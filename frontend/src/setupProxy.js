const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
    app.use('/api/v3', createProxyMiddleware({
        target: 'https://ark.cn-beijing.volces.com',
        changeOrigin: true,
        pathRewrite: {
            '^/api/v3': '/api/v3'
        }
    }));
};