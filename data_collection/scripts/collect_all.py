from collection_worker.cli import app

if __name__ == "__main__":
    app(prog_name="collect-all", args=["collect-all", *__import__("sys").argv[1:]])
