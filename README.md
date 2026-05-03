# tools

个人工具代码库，收录各类实用工具。

## 环境准备

- Python 3.10+
- pip

## 使用

```bash
git clone git@github.com:menghaoze1206-hash/tools.git
cd tools
```

## 工具列表

### linux-upload

简易的 Linux 文件上传服务。通过 Web UI 浏览服务器目录、拖放或选择文件/文件夹上传。

- 单文件上限 500MB
- 目录浏览限定在用户 home 目录内
- 上传路径穿越防护

#### 快速启动

```bash
cd linux-upload
pip3 install -r requirements.txt
python3 -m uvicorn main:app --port 8787
```

#### 启用认证

```bash
AUTH_TOKEN=your-secret-token python3 -m uvicorn main:app --port 8787
```

设置后，API 请求需要携带 `Authorization: Bearer your-secret-token` 头。网页 UI 需在浏览器控制台设置 token：

```js
localStorage.setItem('auth_token', 'your-secret-token')
```

#### 运行测试

```bash
pip3 install pytest httpx
python3 -m pytest test_main.py -v
```

#### 生产环境部署

```bash
python3 -m uvicorn main:app \
  --host 0.0.0.0 \
  --port 8787 \
  --workers 4 \
  --proxy-headers \
  --log-level info
```

建议配合 Nginx 反向代理和 systemd 托管运行。

#### Docker

```bash
docker build -t linux-upload .
docker run -d -p 8787:8787 \
  -v /path/to/uploads:/app/uploads \
  -e AUTH_TOKEN=your-secret-token \
  linux-upload
```
