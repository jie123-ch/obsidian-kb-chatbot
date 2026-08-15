import uvicorn

if __name__ == "__main__":
    # 仅本机访问；如需局域网其他设备访问，把 host 改为 "0.0.0.0"
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
