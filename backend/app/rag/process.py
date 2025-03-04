import asyncio
import logging
from app.database import get_async_db
from app.models.rag import RagFile, RagFileStatus
from app.rag.parser import get_parser
from app.rag.rag_api import rag_api
from sqlalchemy import update, select

logger = logging.getLogger("app")

rag_content_queue = asyncio.Queue()
rag_summary_queue = asyncio.Queue()
rag_upload_queue = asyncio.Queue()
rag_parsing_queue = asyncio.Queue()

async def get_rag_task():
    while True:
        await asyncio.sleep(5)

        try:
            files_to_process = []
            status_updates = []  # 存储需要更新的状态信息
            
            # 修改这里的数据库会话获取方式
            async with get_async_db() as db:
                try:
                    async with db.begin():  # 开始一个事务上下文
                        # 1. 查询并锁定记录
                        stmt = (
                            select(RagFile)
                            .where(RagFile.status.in_([
                                RagFileStatus.LOCAL_SAVED,
                                # RagFileStatus.LOCAL_PARSED,
                                # RagFileStatus.LLM_SUMMARYED,
                                RagFileStatus.RAG_UPLOADED
                            ]))
                            .limit(15)
                            .with_for_update(skip_locked=True)
                        )
                        
                        result = await db.execute(stmt)
                        files = result.scalars().all()
                        
                        if not files:
                            continue
                        
                        # 2. 在同一事务中更新状态
                        status_map = {
                            # RagFileStatus.LOCAL_SAVED: RagFileStatus.LOCAL_PARSING,
                            # RagFileStatus.LOCAL_PARSED: RagFileStatus.LLM_SUMMARIZING,
                            # RagFileStatus.LLM_SUMMARYED: RagFileStatus.RAG_UPLOADING,
                            # RagFileStatus.RAG_UPLOADED: RagFileStatus.RAG_PARSING,
                            RagFileStatus.LOCAL_SAVED: RagFileStatus.RAG_UPLOADING,
                            RagFileStatus.RAG_UPLOADED: RagFileStatus.RAG_PARSING,
                        }
                        
                        for file in files:
                            next_status = status_map.get(file.status)
                            if next_status:
                                stmt = (
                                    update(RagFile)
                                    .where(RagFile.file_id == file.file_id)
                                    .values(status=next_status)
                                )
                                await db.execute(stmt)
                                # 保存文件对象和新状态，用于后续队列处理
                                file.status = next_status
                                status_updates.append((file, next_status))
                    
                    files_to_process = status_updates
                    
                except Exception as e:
                    logger.error(f"get_rag_task 数据库操作失败: {str(e)}")
                    continue
            
            # 事务已提交，开始处理队列
            for file, next_status in files_to_process:
                try:
                    queue_map = {
                        # RagFileStatus.LOCAL_PARSING: rag_content_queue,
                        # RagFileStatus.LLM_SUMMARIZING: rag_summary_queue,
                        RagFileStatus.RAG_UPLOADING: rag_upload_queue,
                        RagFileStatus.RAG_PARSING: rag_parsing_queue,
                    }
                    
                    if next_status in queue_map:
                        await asyncio.wait_for(
                            queue_map[next_status].put(file), 
                            timeout=1.0
                        )
                        logger.info(f"get_rag_task 获取RAG文件任务: {file.file_id} {file.file_name} {file.status} -> {next_status}")
                        
                except asyncio.TimeoutError:
                    logger.error(f"get_rag_task 队列已满，跳过任务: {file.file_id}")
                    continue
                except Exception as e:
                    logger.error(f"get_rag_task 推送队列时发生错误: {file.file_id} - {str(e)}")
                    continue

            logger.info(f"get_rag_task 当前队列大小: content={rag_content_queue.qsize()} summary={rag_summary_queue.qsize()} upload={rag_upload_queue.qsize()} parsing={rag_parsing_queue.qsize()}")
                
        except Exception as e:
            logger.error(f"get_rag_task 获取RAG文件任务时发生错误: {str(e)}")
            await asyncio.sleep(5)

async def rag_content_task(queue: asyncio.Queue, semaphore: asyncio.Semaphore):
    while True:
        rag_file = None
        try:
            # 1. 从队列中获取任务
            rag_file = await queue.get()
            logger.info(f"rag_content_task 成功从队列获取任务: {rag_file.file_id} {rag_file.file_name}")

            # 2. 限制并发数处理任务
            async with semaphore:
                # 获取对应的解析器
                parser = get_parser(rag_file.file_ext)
                if not parser:
                    logger.error(f"rag_content_task 找不到文件类型 {rag_file.file_ext} 的解析器")
                    await update_file_status(
                        rag_file.file_id,
                        RagFileStatus.FAILED,
                        f"rag_content_task 找不到文件类型 {rag_file.file_ext} 的解析器"
                    )
                    continue

                # 解析文件内容
                content = await parser.content(rag_file.file_path)

                # 使用异步上下文管理器和事务上下文管理器更新数据库
                async with get_async_db() as db:
                    async with db.begin():
                        stmt = (
                            update(RagFile)
                            .where(RagFile.file_id == rag_file.file_id)
                            .values(
                                content=content,
                                status=RagFileStatus.LOCAL_PARSED,
                                file_words=len(content)
                            )
                        )
                        await db.execute(stmt)
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
            # 1. 从队列中获取任务
            rag_file = await queue.get()
            logger.info(f"rag_summary_task 成功从队列获取任务: {rag_file.file_id} {rag_file.file_name}")
            
            # 2. 限制并发数处理任务
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
                    continue

                # 生成摘要
                summary = await parser.summary(rag_file.content, length="small")
                
                # 使用异步上下文管理器和事务上下文更新数据库
                async with get_async_db() as db:
                    async with db.begin():
                        stmt = (
                            update(RagFile)
                            .where(RagFile.file_id == rag_file.file_id)
                            .values(
                                summary_small=summary,
                                status=RagFileStatus.LLM_SUMMARYED,
                            )
                        )
                        await db.execute(stmt)
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
            # 1. 从队列中获取任务
            rag_file = await queue.get()
            logger.info(f"rag_upload_task 成功从队列获取任务: {rag_file.file_id} {rag_file.file_name}") 
            
            # 2. 限制并发数处理任务
            async with semaphore:
                # 上传文件到知识库
                resp = rag_api.upload_files(rag_file.kb_id, [rag_file.file_path], mode="strong")
                if resp.get("code") != 200 or len(resp.get("data")) == 0:
                    logger.error(f"rag_upload_task 上传文件到知识库失败: {resp.get('msg')}")
                    await update_file_status(
                        rag_file.file_id,
                        RagFileStatus.FAILED,
                        f"rag_upload_task 上传文件到知识库失败: {resp.get('msg')}"
                    )
                    continue
                
                # 使用 SQLAlchemy 异步会话更新数据库
                async with get_async_db() as db:
                    async with db.begin():
                        stmt = (
                            update(RagFile)
                            .where(RagFile.file_id == rag_file.file_id)
                            .values(
                                kb_file_id=resp.get("data")[0].get("file_id"),
                                status=RagFileStatus.RAG_UPLOADED
                            )
                        )
                        await db.execute(stmt)
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
        async with get_async_db() as db:
            async with db.begin():
                stmt = (
                    update(RagFile)
                    .where(RagFile.file_id == file_id)
                    .values(status=status, error_message=error_message)
                )
                await db.execute(stmt)
    except Exception as e:
        logger.error(f"update_file_status 更新文件状态失败 {file_id}: {str(e)}")
        
# 知识库文件任务处理线程
def rag_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    tasks = []
    # 任务获取
    tasks.append(get_rag_task())

    # # 文件内容解析
    # max_content_tasks = 2
    # content_semaphore = asyncio.Semaphore(max_content_tasks)
    # for _ in range(max_content_tasks):
    #     tasks.append(rag_content_task(rag_content_queue, content_semaphore))

    # # 文件摘要
    # max_summary_tasks = 4
    # summary_semaphore = asyncio.Semaphore(max_summary_tasks)
    # for _ in range(max_summary_tasks):
    #     tasks.append(rag_summary_task(rag_summary_queue, summary_semaphore))

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
    