import asyncio
import logging
from app.database import async_pool
from app.models.rag import RagFile, RagFileStatus
from app.rag.parser import get_parser
from app.rag.rag_api import rag_api

logger = logging.getLogger("app")

rag_content_queue = asyncio.Queue()
rag_summary_queue = asyncio.Queue()
rag_upload_queue = asyncio.Queue()
rag_parsing_queue = asyncio.Queue()

async def get_rag_task():
    while True:
        await asyncio.sleep(5)

        try:
            pool = await async_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # 使用 SELECT FOR UPDATE 锁定行
                    query = """
                        SELECT file_id, kb_id, kb_type, kb_file_id, user_id, file_name, file_ext, file_path, status, content FROM rag_files 
                        WHERE status IN (%s, %s, %s, %s)
                        LIMIT 15 
                        FOR UPDATE SKIP LOCKED
                    """
                    await cursor.execute(query, (
                        RagFileStatus.LOCAL_SAVED,
                        RagFileStatus.LOCAL_PARSED,
                        RagFileStatus.LLM_SUMMARYED,
                        RagFileStatus.RAG_UPLOADED
                    ))
                    files = await cursor.fetchall()
                    
                    if not files:
                        continue
                    
                    # 逐个处理文件，每个文件使用独立事务
                    for file in files:
                        try:
                            await conn.begin()  # 开始单个文件的事务
                            
                            # 将元组转换为对象以便使用
                            file_obj = RagFile()
                            file_obj.file_id = file[0]      
                            file_obj.kb_id = file[1]
                            file_obj.kb_type = file[2]
                            file_obj.kb_file_id = file[3]
                            file_obj.user_id = file[4]    
                            file_obj.file_name = file[5]    
                            file_obj.file_ext = file[6]    
                            file_obj.file_path = file[7]   
                            file_obj.status = file[8]      
                            file_obj.content = file[9]
                            
                            status_map = {
                                RagFileStatus.LOCAL_SAVED: RagFileStatus.LOCAL_PARSING,
                                RagFileStatus.LOCAL_PARSED: RagFileStatus.LLM_SUMMARIZING,
                                RagFileStatus.LLM_SUMMARYED: RagFileStatus.RAG_UPLOADING,
                                RagFileStatus.RAG_UPLOADED: RagFileStatus.RAG_PARSING,
                            }
                            next_status = status_map.get(file_obj.status)
                            
                            if next_status:
                                update_query = """
                                    UPDATE rag_files 
                                    SET status = %s 
                                    WHERE file_id = %s
                                """
                                await cursor.execute(update_query, (next_status, file_obj.file_id))
                                logger.info(f"get_rag_task 获取RAG文件任务: {file_obj.file_id} {file_obj.file_name} {file_obj.status} -> {next_status}")

                                # 尝试将任务加入队列，设置超时
                                try:
                                    if next_status == RagFileStatus.LOCAL_PARSING:
                                        await asyncio.wait_for(rag_content_queue.put(file_obj), timeout=1.0)
                                    elif next_status == RagFileStatus.LLM_SUMMARIZING:
                                        await asyncio.wait_for(rag_summary_queue.put(file_obj), timeout=1.0)
                                    elif next_status == RagFileStatus.RAG_UPLOADING:
                                        await asyncio.wait_for(rag_upload_queue.put(file_obj), timeout=1.0)
                                    elif next_status == RagFileStatus.RAG_PARSING:
                                        await asyncio.wait_for(rag_parsing_queue.put(file_obj), timeout=1.0)
                                    
                                    await conn.commit()  # 提交单个文件的事务
                                except asyncio.TimeoutError:
                                    await conn.rollback()  # 队列操作超时，回滚当前文件的事务
                                    logger.warning(f"get_rag_task 队列已满，跳过任务: {file_obj.file_id}")
                                    continue
                                
                        except Exception as e:
                            await conn.rollback()  # 处理单个文件发生错误时回滚
                            logger.error(f"get_rag_task 处理文件 {file[0]} 时发生错误: {str(e)}")
                            continue
                            
                    logger.info(f"get_rag_task 当前队列大小: content={rag_content_queue.qsize()} summary={rag_summary_queue.qsize()} upload={rag_upload_queue.qsize()} parsing={rag_parsing_queue.qsize()}")
                    
        except Exception as e:
            logger.error(f"get_rag_task 获取RAG文件任务时发生错误: {str(e)}")
            await asyncio.sleep(5)  # 发生错误时等待5秒后重试

async def rag_content_task(queue: asyncio.Queue, semaphore: asyncio.Semaphore):
    while True:
        rag_file = None
        try:
            # 1. 获取任务 - 使用异步等待而不是立即检查
            rag_file = await queue.get()
            logger.info(f"rag_content_task 成功从队列获取任务: {rag_file.file_id} {rag_file.file_name}")

            # 2. 处理任务
            async with semaphore:
                # 获取解析器
                parser = get_parser(rag_file.file_ext)
                if not parser:
                    logger.error(f"rag_content_task 找不到文件类型 {rag_file.file_ext} 的解析器")
                    await update_file_status(
                        rag_file.file_id,
                        RagFileStatus.FAILED,
                        f"rag_content_task 找不到文件类型 {rag_file.file_ext} 的解析器"
                    )
                    queue.task_done()
                    continue

                # 解析内容
                content = await parser.content(rag_file.file_path)

                # 更新数据库
                pool = await async_pool()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await conn.begin()
                        await cursor.execute(
                            "UPDATE rag_files SET content = %s, status = %s, file_words = %s WHERE file_id = %s",
                            (content, RagFileStatus.LOCAL_PARSED, len(content), rag_file.file_id)
                        )
                        await conn.commit()
                        logger.info(f"rag_content_task 文件内容处理完成: {rag_file.file_id}")

        except Exception as e:
            logger.error(f"rag_content_task 处理文件内容时发生错误: {str(e)}")
            if rag_file:
                await update_file_status(
                    rag_file.file_id,
                    RagFileStatus.FAILED,
                    f"rag_content_task 处理文件内容时发生错误: {str(e)}"
                )
                await asyncio.sleep(1)  # 发生错误时短暂等待
        finally:
            if rag_file:
                queue.task_done()

async def rag_summary_task(queue: asyncio.Queue, semaphore: asyncio.Semaphore):
    while True:
        rag_file = None
        try:
            rag_file = await queue.get()
            logger.info(f"rag_summary_task 成功从队列获取任务: {rag_file.file_id} {rag_file.file_name}")
            
            async with semaphore:
                # 获取解析器
                parser = get_parser(rag_file.file_ext)
                if not parser:
                    logger.error(f"rag_summary_task 找不到文件类型 {rag_file.file_ext} 的解析器")
                    await update_file_status(
                        rag_file.file_id,
                        RagFileStatus.FAILED,
                        f"rag_summary_task 找不到文件类型 {rag_file.file_ext} 的解析器"
                    )
                    queue.task_done()
                    continue 
                
                # 生成摘要
                summary = await parser.summary(rag_file.content, length="small")
                
                # 更新数据库
                pool = await async_pool()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await conn.begin()
                        await cursor.execute(
                            "UPDATE rag_files SET summary_small = %s, status = %s WHERE file_id = %s",
                            (summary, RagFileStatus.LLM_SUMMARYED, rag_file.file_id)
                        )
                        await conn.commit()
                        logger.info(f"rag_summary_task 文件摘要处理完成: {rag_file.file_id}")
                        
        except Exception as e:
            logger.error(f"rag_summary_task 处理文件摘要时发生错误: {str(e)}")
            if rag_file:
                await update_file_status(
                    rag_file.file_id,
                    RagFileStatus.FAILED,
                    f"rag_summary_task 处理文件摘要时发生错误: {str(e)}"
                )
                await asyncio.sleep(1)
        finally:
            if rag_file:    
                queue.task_done()

async def rag_upload_task(queue: asyncio.Queue, semaphore: asyncio.Semaphore):
    while True:
        rag_file = None
        try:
            rag_file = await queue.get()
            logger.info(f"rag_upload_task 成功从队列获取任务: {rag_file.file_id} {rag_file.file_name}") 
            
            async with semaphore:
                resp = rag_api.upload_files(rag_file.kb_id, [rag_file.file_path], mode="strong")
                if resp.get("code") != 200 or len(resp.get("data")) == 0:
                    logger.error(f"rag_upload_task 上传文件到知识库失败: {resp.get('msg')}")
                    await update_file_status(
                        rag_file.file_id,
                        RagFileStatus.FAILED,
                        f"rag_upload_task 上传文件到知识库失败: {resp.get('msg')}"
                    )
                    queue.task_done()
                    continue
                
                # 更新数据库
                pool = await async_pool()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await conn.begin()
                        await cursor.execute(
                            "UPDATE rag_files SET kb_file_id = %s, status = %s WHERE file_id = %s",
                            (resp.get("data")[0].get("file_id"), RagFileStatus.RAG_UPLOADED, rag_file.file_id)
                        )
                        await conn.commit()
                        logger.info(f"rag_upload_task 文件上传知识库完成，正在解析: {rag_file.file_id}")
                
        except Exception as e:
            logger.error(f"rag_upload_task 处理文件上传时发生错误: {str(e)}")
            if rag_file:
                await update_file_status(
                    rag_file.file_id,
                    RagFileStatus.FAILED,
                    f"rag_upload_task 处理文件上传时发生错误: {str(e)}"
                )
                await asyncio.sleep(1)
        finally:
            if rag_file:
                queue.task_done()

async def rag_file_poll_task(queue: asyncio.Queue, semaphore: asyncio.Semaphore):
    while True:
        rag_file = None
        try:
            rag_file = await queue.get()
            # logger.info(f"rag_file_poll_task 成功从队列获取任务: {rag_file.file_id} {rag_file.file_name}")

            async with semaphore:
                resp = rag_api.list_files(rag_file.kb_id, file_id=rag_file.kb_file_id)
                details = resp.get("data").get("details")
                if resp.get("code") != 200 or details is None or len(details) == 0:
                    logger.error(f"rag_file_poll_task 查询RAG解析进度失败: {resp.get('msg')}")
                    await update_file_status(
                        rag_file.file_id,
                        RagFileStatus.FAILED,
                        f"rag_file_poll_task 查询RAG解析进度失败: {resp.get('msg')}"
                    )
                    await asyncio.sleep(2)
                    queue.task_done()
                    continue
                detail = details[0]
                if detail.get("status") == "yellow" or detail.get("status") == "gray": # 黄色、灰色表示解析中
                    await asyncio.sleep(2)  # 等待2秒
                    await queue.put(rag_file)  # 重新加入队列
                elif detail.get("status") == "green": # 绿色表示解析完成
                    await update_file_status(
                        rag_file.file_id,
                        RagFileStatus.DONE,
                    )
                elif detail.get("status") == "red": # 红色表示解析失败
                    logger.error(f"rag_file_poll_task 文件RAG解析失败: {rag_file.file_id}")
                    await update_file_status(
                        rag_file.file_id,
                        RagFileStatus.FAILED,
                        f"rag_file_poll_task 文件RAG解析失败: {rag_file.file_id}"
                    )
                else:
                    logger.error(f"rag_file_poll_task 文件RAG解析状态未知: {rag_file.file_id} status: {detail.get('status')}")
                    await update_file_status(
                        rag_file.file_id,
                        RagFileStatus.FAILED,
                        f"rag_file_poll_task 文件RAG解析失败: {rag_file.file_id} 异常状态: {detail.get('status')}"
                    )
        except Exception as e:
            logger.error(f"rag_file_poll_task 查询RAG解析进度时发生错误: {str(e)}")
            if rag_file:
                await update_file_status(
                    rag_file.file_id,
                    RagFileStatus.FAILED,
                    f"rag_file_poll_task 查询RAG解析进度时发生错误: {str(e)}"
                )
                await asyncio.sleep(1)
        finally:
            if rag_file:
                queue.task_done()

async def update_file_status(file_id: str, status: RagFileStatus, error_message: str = ""):
    """更新文件状态的辅助函数"""
    try:
        pool = await async_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await conn.begin()
                await cursor.execute(
                    "UPDATE rag_files SET status = %s, error_message = %s WHERE file_id = %s",
                    (status, error_message, file_id)
                )
                await conn.commit()
    except Exception as e:
        logger.error(f"update_file_status 更新文件状态失败 {file_id}: {str(e)}")
        
# 知识库文件任务处理线程
def rag_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    tasks = []
    # 任务获取
    tasks.append(get_rag_task())

    # 文件内容解析
    max_content_tasks = 2
    content_semaphore = asyncio.Semaphore(max_content_tasks)
    for _ in range(max_content_tasks):
        tasks.append(rag_content_task(rag_content_queue, content_semaphore))

    # 文件摘要
    max_summary_tasks = 4
    summary_semaphore = asyncio.Semaphore(max_summary_tasks)
    for _ in range(max_summary_tasks):
        tasks.append(rag_summary_task(rag_summary_queue, summary_semaphore))

    # 文件上传RAG知识库
    max_upload_tasks = 4
    upload_semaphore = asyncio.Semaphore(max_upload_tasks)
    for _ in range(max_upload_tasks):
        tasks.append(rag_upload_task(rag_upload_queue, upload_semaphore))
    
    # 查询RAG知识库解析进度
    max_poll_tasks = 4
    poll_semaphore = asyncio.Semaphore(max_poll_tasks)
    for _ in range(max_poll_tasks):
        tasks.append(rag_file_poll_task(rag_parsing_queue, poll_semaphore))
        
    loop.run_until_complete(asyncio.gather(*tasks))
    