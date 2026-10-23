import sys

try:
    from .app import App
except ModuleNotFoundError as exc:
    if exc.name == "tkinter":
        raise SystemExit(
            f"{sys.executable} has no tkinter. Use a Python build with Tk installed."
        ) from None
    raise


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
