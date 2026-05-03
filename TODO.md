# TODO

## 安全（高优先级）

- [x] **路径穿越防护**：`download` 和 `delete` 端点未限制文件访问范围，攻击者可通过 `../../../etc/passwd` 读取/删除服务器任意文件。需对路径做 `resolve` 后校验是否在 `UPLOAD_DIR` 子树内。
- [x] **添加认证**：所有接口无任何认证，任何人可浏览目录、上传/下载/删除文件。至少加一个 `--auth-token` 参数做 Bearer token 校验或 HTTP Basic Auth。
- [x] **限制目录浏览范围**：`/api/browse` 可以浏览整个服务器文件系统，应限定在配置的基础目录内。
- [x] **添加 `.gitignore`**：忽略 `uploads/`、`config.json`、`__pycache__/`、`*.pyc`、`.env` 等。
- [x] **上传文件大小限制**：无上限，存在磁盘写满导致 DoS 的风险。

## 代码质量

- [x] **添加 `requirements.txt` 或 `pyproject.toml`**：锁定 fastapi 和 uvicorn 版本。
- [x] **添加测试**：至少覆盖上传、下载、删除的路径穿越防护、配置读写。
- [x] **修复端口不一致**：README 写 `8000`，代码默认 `8787`，统一一下。
- [x] **废弃类型注解替换**：`List[UploadFile]` → `list[UploadFile]`（Python 3.10+）。
- [x] **补充返回类型注解**：`browse_dir`、`get_config`、`upload_files` 等都缺返回类型。
- [x] **不要吞异常**：config 读取、IP 检测等处的 `except Exception: pass` 应至少打日志。
- [x] **`print()` 换成 `logging`**：统一使用 Python logging 模块，支持日志级别和时间戳。
- [x] **上传目录并发安全**：`global UPLOAD_DIR` 在多线程下读写不安全，改用线程安全的方式。

## 前端

- [x] **修复 XSS 风险**：`onclick` 中拼接文件名到 JS 字符串，`esc()` 不防反斜杠。改为事件委托 + `data-*` 属性。
- [x] **`loadFileList()` 加错误处理**：fetch 没有 `.catch()`，服务端挂了 UI 无提示。
- [x] **上传进度展示**：大文件上传时无进度反馈，改用 `XMLHttpRequest.upload.onprogress`。
- [x] **客户端文件大小校验**：入队前检查文件大小并给出提示。
- [x] **目录列表高度可调**：`max-height: 240px` 偏小且不可调整。

## 工程化

- [x] **添加 `--workers`、`--proxy-headers` 等生产环境建议**到 README。
- [x] **考虑添加 Dockerfile**：简化一键部署。
