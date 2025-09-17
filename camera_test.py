if __name__ == "__main__":
    handler = CameraFeedHandler(use_cuda=True)
    handler.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        handler.stop()
