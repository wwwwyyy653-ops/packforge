"""启动后端服务：python run.py [port]"""
import os
import sys

import uvicorn

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    os.environ.setdefault("PACKFORGE_HOME", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".data"))
    print(f"后端服务启动: http://127.0.0.1:{port}  (文档 /docs)")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=False)
