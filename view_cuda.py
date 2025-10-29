#!/usr/bin/env python3
"""
Проверка версий: CUDA, PyTorch, torchaudio, torchvision
"""

import importlib
import sys

def try_import(name):
    try:
        return importlib.import_module(name)
    except Exception as e:
        return None

def fmt(val):
    return str(val) if val is not None else "не установлен / недоступно"

def main():
    torch = try_import("torch")
    torchaudio = try_import("torchaudio")
    torchvision = try_import("torchvision")

    print("=== PyTorch / CUDA / related info ===\n")

    if torch is None:
        print("torch: НЕ УСТАНОВЛЕН")
    else:
        print(f"torch.__version__: {fmt(torch.__version__)}")

        # CUDA runtime version reported by PyTorch (string or None)
        cuda_ver = getattr(torch.version, "cuda", None)
        print(f"torch.version.cuda (runtime reported): {fmt(cuda_ver)}")

        # Is CUDA available according to PyTorch?
        try:
            cuda_available = torch.cuda.is_available()
        except Exception:
            cuda_available = False
        print(f"torch.cuda.is_available(): {fmt(cuda_available)}")

        # If CUDA available, show device count, current device and name
        if cuda_available:
            try:
                dev_count = torch.cuda.device_count()
            except Exception:
                dev_count = "unknown"
            print(f"CUDA device count: {fmt(dev_count)}")

            try:
                cur = torch.cuda.current_device()
                name = torch.cuda.get_device_name(cur)
                props = torch.cuda.get_device_properties(cur)
                cc = f"{props.major}.{props.minor}" if hasattr(props, "major") else "unknown"
                total_mem = getattr(props, "total_memory", None)
                if total_mem:
                    total_mem_mb = int(total_mem / (1024**2))
                    mem_str = f"{total_mem_mb} MB"
                else:
                    mem_str = "unknown"
                print(f"Current CUDA device index: {cur}")
                print(f"Current CUDA device name: {name}")
                print(f"Compute capability: {cc}")
                print(f"Total device memory: {mem_str}")
            except Exception as e:
                print(f"Информация о CUDA-устройстве недоступна: {e}")

        # cuDNN
        try:
            cudnn_ver = torch.backends.cudnn.version()
        except Exception:
            cudnn_ver = None
        print(f"torch.backends.cudnn.version(): {fmt(cudnn_ver)}")

    print("\n=== torchaudio ===")
    if torchaudio is None:
        print("torchaudio: НЕ УСТАНОВЛЕН")
    else:
        # Some torchaudio versions expose __version__, older might not
        ver = getattr(torchaudio, "__version__", None)
        print(f"torchaudio.__version__: {fmt(ver)}")

    print("\n=== torchvision ===")
    if torchvision is None:
        print("torchvision: НЕ УСТАНОВЛЕН")
    else:
        ver = getattr(torchvision, "__version__", None)
        print(f"torchvision.__version__: {fmt(ver)}")

    print("\n=== Доп. советы ===")
    print("Если хотите также увидеть версию установленного nvcc (CUDA toolkit), выполните в терминале:")
    print("  nvcc --version")
    print("или (если nvcc недоступен) посмотрeть содержимое /usr/local/cuda/version.txt или аналогичного пути.")

if __name__ == "__main__":
    main()
