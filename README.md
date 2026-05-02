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

```bash
cd linux-upload
pip3 install fastapi uvicorn
python3 -m uvicorn main:app --port 8787
```

### 生产环境部署

```bash
# 多 worker 进程 + 信任反向代理头
python3 -m uvicorn main:app \
  --host 0.0.0.0 \
  --port 8787 \
  --workers 4 \
  --proxy-headers \
  --log-level info
```

建议配合 Nginx 反向代理和 systemd 托管运行。
