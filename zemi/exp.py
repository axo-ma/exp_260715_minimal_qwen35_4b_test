from __future__ import annotations

import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


HOST = "127.0.0.1"
PORT = 8080
HEALTH_URL = f"http://{HOST}:{PORT}/health"

DEFAULT_SERVER_PATH = Path(r".\llama.cpp\llama-server.exe")
DEFAULT_MODEL_PATH = Path(r".\models\Qwen_Qwen3.5-4B-Q4_K_M.gguf")
DEFAULT_MODEL_ALIAS = "qwen3.5-4b"

_server: subprocess.Popen | None = None


def is_ready(timeout: float = 1.0) -> bool:
    """Проверяет, отвечает ли llama-server на /health."""
    try:
        with urlopen(HEALTH_URL, timeout=timeout):
            return True
    except (URLError, TimeoutError):
        return False


def _find_and_stop_process_on_port() -> bool:
    """Находит и останавливает llama-server, слушающий PORT."""
    command = f"""
    $connection = Get-NetTCPConnection `
        -LocalPort {PORT} `
        -State Listen `
        -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $connection) {{
        Write-Output "NOT_FOUND"
        exit
    }}

    $process = Get-Process `
        -Id $connection.OwningProcess `
        -ErrorAction SilentlyContinue

    if (-not $process) {{
        Write-Output "NOT_FOUND"
        exit
    }}

    if ($process.ProcessName -ne "llama-server") {{
        Write-Output "WRONG_PROCESS:$($process.ProcessName):$($process.Id)"
        exit
    }}

    Stop-Process -Id $process.Id -Force
    Write-Output "STOPPED:$($process.Id)"
    """

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout.strip()

    if output.startswith("STOPPED:"):
        pid = output.split(":", 1)[1]
        print(f"llama-server остановлен, PID: {pid}")
        return True

    if output == "NOT_FOUND":
        return False

    if output.startswith("WRONG_PROCESS:"):
        _, process_name, pid = output.split(":", 2)
        raise RuntimeError(
            f"Порт {PORT} занят другим процессом: "
            f"{process_name}, PID: {pid}"
        )

    error = result.stderr.strip() or output or "неизвестная ошибка"
    raise RuntimeError(
        f"Не удалось проверить процесс на порту {PORT}: {error}"
    )


def _wait_until_stopped(timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if not is_ready():
            return
        time.sleep(0.2)

    raise TimeoutError(
        f"llama-server не остановился за {timeout:.1f} секунд"
    )


def stop(timeout: float = 10.0) -> bool:
    """Останавливает llama-server независимо от того, кем он был запущен."""
    global _server

    stopped = False

    if _server is not None and _server.poll() is None:
        _server.terminate()

        try:
            _server.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _server.kill()
            _server.wait()

        print(f"llama-server остановлен, PID: {_server.pid}")
        stopped = True

    _server = None

    if is_ready():
        stopped = _find_and_stop_process_on_port() or stopped

    if stopped:
        _wait_until_stopped(timeout)
    else:
        print("Работающий llama-server не найден")

    return stopped


def start(
    *,
    server_path: str | Path = DEFAULT_SERVER_PATH,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    alias: str = DEFAULT_MODEL_ALIAS,
    ctx_size: int = 4096,
    threads: int = 4,
    threads_batch: int = 4,
    reasoning: str = "off",
    startup_timeout: float = 120.0,
) -> subprocess.Popen:
    """Запускает llama-server и ждёт готовности /health."""
    global _server

    if is_ready():
        raise RuntimeError(
            f"llama-server уже работает на {HOST}:{PORT}. "
            "Для перезапуска используй exp.restart()."
        )

    server_path = Path(server_path)
    model_path = Path(model_path)

    if not server_path.is_file():
        raise FileNotFoundError(
            f"llama-server.exe не найден: {server_path.resolve()}"
        )

    if not model_path.is_file():
        raise FileNotFoundError(
            f"Файл модели не найден: {model_path.resolve()}"
        )

    _server = subprocess.Popen([
        str(server_path),
        "--model", str(model_path),
        "--alias", alias,
        "--host", HOST,
        "--port", str(PORT),
        "--ctx-size", str(ctx_size),
        "--threads", str(threads),
        "--threads-batch", str(threads_batch),
        "--reasoning", reasoning,
    ])

    deadline = time.monotonic() + startup_timeout

    while time.monotonic() < deadline:
        if _server.poll() is not None:
            return_code = _server.returncode
            _server = None
            raise RuntimeError(
                f"llama-server завершился с кодом {return_code}"
            )

        if is_ready():
            print(f"llama-server запущен и готов, PID: {_server.pid}")
            return _server

        time.sleep(1)

    process = _server
    _server = None

    if process.poll() is None:
        process.terminate()

    raise TimeoutError(
        f"llama-server не запустился за {startup_timeout:.1f} секунд"
    )


def restart(**kwargs) -> subprocess.Popen:
    """Останавливает текущий llama-server и запускает новый."""
    stop()
    return start(**kwargs)

def print_response(response) -> str:
    """Печатает ответ модели и статистику llama.cpp."""

    text = response.choices[0].message.content

    if text is None:
        raise RuntimeError("Модель вернула пустой ответ")

    print(text)

    usage = response.usage
    model_extra = response.model_extra or {}
    timings = model_extra.get("timings", {})

    print("\nСтатистика:")

    if usage is not None:
        print(f"Токены промпта:      {usage.prompt_tokens}")
        print(f"Токены генерации:    {usage.completion_tokens}")
        print(f"Всего токенов:       {usage.total_tokens}")
    else:
        print("Статистика токенов отсутствует")

    prompt_ms = timings.get("prompt_ms")
    prompt_per_second = timings.get("prompt_per_second")
    predicted_ms = timings.get("predicted_ms")
    predicted_per_second = timings.get("predicted_per_second")

    if prompt_ms is not None:
        print(f"Время префилла:      {prompt_ms / 1000:.2f} с")

    if prompt_per_second is not None:
        print(
            f"Скорость префилла:   "
            f"{prompt_per_second:.2f} ток/с"
        )

    if predicted_ms is not None:
        print(f"Время генерации:     {predicted_ms / 1000:.2f} с")

    if predicted_per_second is not None:
        print(
            f"Скорость генерации:  "
            f"{predicted_per_second:.2f} ток/с"
        )

    return text
