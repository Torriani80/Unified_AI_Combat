import sys, os, json
try:
    import wmi
    print("wmi: INSTALADO")
    c = wmi.WMI()
    cpu = c.Win32_Processor()[0]
    print(f"CPU: {cpu.Name}")
    cpu_temp = getattr(cpu, 'Temperature', 'SEM ATRIBUTO')
    print(f"CPU Temp attr: {cpu_temp}")
    gpu = c.Win32_VideoController()[0]
    print(f"GPU: {gpu.Name}")
    gpu_temp = getattr(gpu, 'Temperature', 'SEM ATRIBUTO')
    print(f"GPU Temp attr: {gpu_temp}")
    ram = c.Win32_ComputerSystem()[0]
    total_ram = int(ram.TotalPhysicalMemory) / (1024**3)
    print(f"RAM: {total_ram:.1f} GB")
except ImportError:
    print("wmi: NAO INSTALADO - hardware info NAO funciona")
except Exception as e:
    print(f"ERRO: {e}")
