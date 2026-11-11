#!/usr/bin/env python3
"""p2pcheck.py - find why vLLM tensor parallel hangs on a multi-GPU PCIe box.

Runs each check in its own child process with a timeout, so a hang is
reported as HANG instead of freezing your terminal:

  1. host     IOMMU mode of each GPU, ACS on the bridges above it, VM,
              container, /dev/shm size
  2. topo     nvidia-smi topo -m and the driver's P2P read/write report
  3. peer     torch.cuda.can_device_access_peer for every pair
  4. ipc      the CUDA IPC write test vLLM runs with VLLM_SKIP_P2P_CHECK=0
              (1 KiB), and the same test at 64 MiB
  5. copy     a 256 MiB GPU-to-GPU copy, checked byte for byte, with GB/s
  6. nccl     all-reduce from 512 B to 64 MiB with NCCL defaults, with
              NCCL_P2P_DISABLE=1, and (if needed) NCCL_CUMEM_HOST_ENABLE=0,
              plus the transport NCCL picked ("via P2P/IPC", "via SHM", ...)
  7. vllm     (with --vllm) vLLM's own tensor-parallel all-reduce, with and
              without custom all-reduce

Then it prints a verdict and the flags to pass to vLLM.

Usage:
  python3 p2pcheck.py                 # GPUs 0 and 1
  python3 p2pcheck.py --gpus 0,1,2,3
  python3 p2pcheck.py --vllm          # also run vLLM's all-reduce (vLLM installed)
  python3 p2pcheck.py --json report.json

Needs: Linux, NVIDIA driver, Python 3.9+, PyTorch with CUDA. No other packages.
Run it in the same environment (venv / container) that runs vLLM.
Some host checks (ACS) need root; they report "unknown" otherwise.

Source and explanation: https://erimaki-kobo.github.io/en/vllm-consumer-multi-gpu-p2p-check/
License: MIT
"""

import argparse
import ctypes
import glob
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

VERSION = "1.0.0"
MiB = 1 << 20
NCCL_SIZES = [512, 64 * 1024, 1 * MiB, 8 * MiB, 64 * MiB]

# ---------------------------------------------------------------- utilities


def run_cmd(cmd, timeout=20):
    """Run a command, return (returncode, stdout+stderr). Never raises."""
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout, universal_newlines=True)
        return p.returncode, p.stdout
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""
    except Exception as e:  # pragma: no cover
        return 1, str(e)


def read_text(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return None


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_child(stage, args, extra_env=None, timeout=60):
    """Run `python3 p2pcheck.py --_child <stage>` with a timeout.

    Returns dict with status in PASS/FAIL/HANG/ERROR plus whatever the child
    wrote, and the tail of its log.
    """
    out = tempfile.NamedTemporaryFile(prefix="p2pcheck_", suffix=".json", delete=False)
    out.close()
    log = tempfile.NamedTemporaryFile(prefix="p2pcheck_", suffix=".log", delete=False)
    log.close()
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, os.path.abspath(__file__), "--_child", stage,
           "--_out", out.name, "--gpus", ",".join(map(str, args.gpus)),
           "--backend", args.backend]
    t0 = time.time()
    with open(log.name, "w") as lf:
        p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env,
                             start_new_session=True)
        try:
            p.wait(timeout=timeout)
            hung = False
        except subprocess.TimeoutExpired:
            hung = True
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except Exception:
                p.kill()
            p.wait()
    elapsed = time.time() - t0
    logtext = read_text(log.name) or ""
    result = {}
    txt = read_text(out.name)
    if txt:
        try:
            result = json.loads(txt)
        except ValueError:
            result = {}
    for f in (out.name, log.name):
        try:
            os.unlink(f)
        except OSError:
            pass
    if hung:
        result["status"] = "HANG"
        result["detail"] = "no result after %ds (killed)" % timeout
    elif "status" not in result:
        result["status"] = "ERROR"
        result["detail"] = "child exited with code %s" % p.returncode
    result["seconds"] = round(elapsed, 1)
    result["log_tail"] = logtext[-4000:]
    result["transports"] = sorted(set(parse_nccl_transports(logtext)))
    result["cuda_217"] = bool(re.search(r"Cuda failure 217|peer access is not supported", logtext))
    return result


def parse_nccl_transports(text):
    """NCCL_DEBUG=INFO prints e.g. 'Channel 00/0 : 0[0] -> 1[1] via P2P/CUMEM/read'."""
    return re.findall(r"->\s*\d+\[\w+\]\s+via\s+([A-Za-z0-9_/]+)", text)


# ---------------------------------------------------------------- host checks


def pci_sysfs_id(bus_id):
    """nvidia-smi '00000000:01:00.0' -> sysfs '0000:01:00.0'."""
    m = re.match(r"^([0-9A-Fa-f]+):([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})\.([0-7])$", bus_id.strip())
    if not m:
        return None
    dom, bus, dev, fn = m.groups()
    return ("%04x:%s:%s.%s" % (int(dom, 16) & 0xFFFF, bus, dev, fn)).lower()


def parse_gpu_query(text):
    gpus = []
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4 or not parts[0].isdigit():
            continue
        gpus.append({"index": int(parts[0]), "name": parts[1], "bus_id": parts[2],
                     "driver": parts[3],
                     "compute_cap": parts[4] if len(parts) > 4 else None})
    return gpus


def parse_matrix(text):
    """Parse nvidia-smi 'topo -m' or 'topo -p2p r' matrices -> {(i,j): code}."""
    lines = [l for l in text.splitlines() if l.strip()]
    header = None
    out = {}
    for l in lines:
        toks = l.split()
        if header is None:
            # header row: "GPU0 GPU1 ... CPU Affinity ..." (first two tokens are GPUs)
            if len(toks) >= 2 and re.match(r"^GPU\d+$", toks[0]) and re.match(r"^GPU\d+$", toks[1]):
                header = [int(t[3:]) for t in toks if re.match(r"^GPU\d+$", t)]
            continue
        if not toks or not re.match(r"^GPU\d+$", toks[0]):
            if header is not None and out:
                break
            continue
        i = int(toks[0][3:])
        for k, j in enumerate(header):
            if k + 1 < len(toks):
                out[(i, j)] = toks[k + 1]
    return out


def iommu_info(sysfs_ids):
    info = {"cmdline": [], "iommu_present": None, "group_type": {}}
    cmd = read_text("/proc/cmdline") or ""
    info["cmdline"] = [t for t in cmd.split() if re.match(r"^(iommu|intel_iommu|amd_iommu)=", t)]
    if os.path.isdir("/sys/class/iommu"):
        info["iommu_present"] = len(os.listdir("/sys/class/iommu")) > 0
    for sid in sysfs_ids:
        if not sid:
            continue
        t = read_text("/sys/bus/pci/devices/%s/iommu_group/type" % sid)
        info["group_type"][sid] = t.strip() if t else None
    return info


def iommu_translated(info):
    """True if any GPU sits in a translated (DMA) IOMMU domain."""
    types = [t for t in info["group_type"].values() if t]
    if types:
        return any(t.upper().startswith("DMA") for t in types)
    if info["iommu_present"] is False:
        return False
    return None


def upstream_bridges(sid):
    try:
        real = os.path.realpath("/sys/bus/pci/devices/%s" % sid)
    except Exception:
        return []
    parts = real.split("/")
    ids = [p for p in parts if re.match(r"^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]$", p)]
    return ids[:-1]  # drop the GPU itself


def acs_info(sysfs_ids):
    """Return {bridge: 'on'|'off'|'none'|'unknown'} for bridges above each GPU."""
    res = {}
    if not shutil.which("lspci"):
        return {"_": "lspci not installed"}
    for sid in sysfs_ids:
        for br in upstream_bridges(sid or ""):
            if br in res:
                continue
            rc, out = run_cmd(["lspci", "-vvv", "-s", br])
            if rc != 0:
                res[br] = "unknown"
            elif "ACSCtl:" in out:
                line = [l for l in out.splitlines() if "ACSCtl:" in l][0]
                res[br] = "on" if "SrcValid+" in line else "off"
            elif "Capabilities: <access denied>" in out:
                res[br] = "unknown (run as root)"
            else:
                res[br] = "none"
    return res


def virt_info():
    v = {"hypervisor": None, "wsl": False, "container": None}
    if shutil.which("systemd-detect-virt"):
        rc, out = run_cmd(["systemd-detect-virt", "--vm"])
        out = out.strip()
        v["hypervisor"] = out if rc == 0 and out and out != "none" else None
    if v["hypervisor"] is None:
        cpu = read_text("/proc/cpuinfo") or ""
        if re.search(r"^flags\s*:.*\bhypervisor\b", cpu, re.M):
            v["hypervisor"] = "yes (cpu flag)"
    ver = (read_text("/proc/version") or "").lower()
    v["wsl"] = "microsoft" in ver
    if os.path.exists("/.dockerenv"):
        v["container"] = "docker"
    elif os.path.exists("/run/.containerenv"):
        v["container"] = "podman"
    else:
        cg = read_text("/proc/1/cgroup") or ""
        if re.search(r"docker|kubepods|containerd|libpod", cg):
            v["container"] = "yes"
    return v


def shm_bytes():
    try:
        st = os.statvfs("/dev/shm")
        return st.f_blocks * st.f_frsize
    except Exception:
        return None


# ---------------------------------------------------------------- children


def child_peer(args):
    import torch
    n = torch.cuda.device_count()
    res = {"device_count": n, "torch": torch.__version__,
           "torch_cuda": torch.version.cuda, "nccl": None, "peer": {}, "cap": {}}
    try:
        v = torch.cuda.nccl.version()
        res["nccl"] = ".".join(map(str, v)) if isinstance(v, tuple) else str(v)
    except Exception:
        pass
    try:
        from importlib import metadata
        res["vllm"] = metadata.version("vllm")
    except Exception:
        res["vllm"] = None
    for i in args.gpus:
        if i >= n:
            raise SystemExit("GPU %d not visible (device_count=%d)" % (i, n))
        res["cap"][str(i)] = "%d.%d" % torch.cuda.get_device_capability(i)
        for j in args.gpus:
            if i != j:
                res["peer"]["%d->%d" % (i, j)] = bool(torch.cuda.can_device_access_peer(i, j))
    res["status"] = "PASS"
    return res


def _load_cudart():
    import torch  # loads the libcudart that PyTorch uses; no CUDA context is created
    maps = read_text("/proc/self/maps") or ""
    paths = sorted(set(m for m in re.findall(r"(/\S*libcudart\.so[.\d]*)", maps)))
    tdir = os.path.dirname(os.path.dirname(torch.__file__))
    paths += sorted(glob.glob(os.path.join(tdir, "nvidia", "*", "lib", "libcudart.so*")))
    paths += sorted(glob.glob(os.path.join(tdir, "nvidia", "cuda_runtime", "lib", "libcudart.so*")))
    cands = paths + ["libcudart.so", "libcudart.so.13", "libcudart.so.12"]
    for p in cands:
        try:
            return ctypes.CDLL(p)
        except OSError:
            continue
    raise RuntimeError("libcudart not found (PyTorch built with static cudart?)")


class _Handle(ctypes.Structure):
    _fields_ = [("reserved", ctypes.c_byte * 64)]


def _ck(lib, rc, what):
    if rc != 0:
        lib.cudaGetErrorString.restype = ctypes.c_char_p
        raise RuntimeError("%s failed: %s" % (what, lib.cudaGetErrorString(rc).decode()))


def _ipc_producer(pairs, nbytes, q_to_cons, q_to_prod, q_res):
    lib = _load_cudart()
    for src, _tgt in pairs:
        _ck(lib, lib.cudaSetDevice(src), "cudaSetDevice")
        ptr = ctypes.c_void_p()
        _ck(lib, lib.cudaMalloc(ctypes.byref(ptr), ctypes.c_size_t(nbytes)), "cudaMalloc")
        _ck(lib, lib.cudaMemset(ptr, 1, ctypes.c_size_t(nbytes)), "cudaMemset")
        _ck(lib, lib.cudaDeviceSynchronize(), "sync")
        h = _Handle()
        _ck(lib, lib.cudaIpcGetMemHandle(ctypes.byref(h), ptr), "cudaIpcGetMemHandle")
        q_to_cons.put(bytes(h.reserved))
        opened = q_to_prod.get()
        ok = False
        if opened:
            q_to_prod.get()  # consumer finished writing
            buf = (ctypes.c_char * nbytes)()
            _ck(lib, lib.cudaMemcpy(buf, ptr, ctypes.c_size_t(nbytes), 4), "cudaMemcpy")
            ok = bytes(buf).count(b"\x02") == nbytes
        q_res.put(("producer", src, ok))
        lib.cudaFree(ptr)
        lib.cudaDeviceReset()


def _ipc_consumer(pairs, nbytes, q_to_cons, q_to_prod, q_res):
    lib = _load_cudart()
    for _src, tgt in pairs:
        _ck(lib, lib.cudaSetDevice(tgt), "cudaSetDevice")
        raw = q_to_cons.get()
        h = _Handle()
        ctypes.memmove(h.reserved, raw, 64)
        ptr = ctypes.c_void_p()
        rc = lib.cudaIpcOpenMemHandle(ctypes.byref(ptr), h, ctypes.c_uint(1))
        opened = rc == 0
        q_to_prod.put(opened)
        ok = False
        if opened:
            _ck(lib, lib.cudaMemset(ptr, 2, ctypes.c_size_t(nbytes)), "cudaMemset(peer)")
            _ck(lib, lib.cudaDeviceSynchronize(), "sync")
            q_to_prod.put(0)
            buf = (ctypes.c_char * nbytes)()
            _ck(lib, lib.cudaMemcpy(buf, ptr, ctypes.c_size_t(nbytes), 4), "cudaMemcpy")
            ok = bytes(buf).count(b"\x02") == nbytes
            lib.cudaIpcCloseMemHandle(ptr)
        q_res.put(("consumer", tgt, ok))
        lib.cudaDeviceReset()


def child_ipc(args, nbytes):
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    pairs = [(i, j) for i in args.gpus for j in args.gpus if i != j]
    q1, q2, q3 = ctx.Queue(), ctx.Queue(), ctx.Queue()
    pp = ctx.Process(target=_ipc_producer, args=(pairs, nbytes, q1, q2, q3))
    pc = ctx.Process(target=_ipc_consumer, args=(pairs, nbytes, q1, q2, q3))
    pp.start()
    pc.start()
    pp.join()
    pc.join()
    if pp.exitcode != 0 or pc.exitcode != 0:
        return {"status": "ERROR", "detail": "test process crashed (see log)"}
    got = {}
    for _ in range(2 * len(pairs)):
        try:
            who, dev, ok = q3.get(timeout=5)
        except Exception:
            break
        got.setdefault(who, []).append(ok)
    res = {"pairs": {}}
    for k, (i, j) in enumerate(pairs):
        a = got.get("producer", [False] * len(pairs))[k]
        b = got.get("consumer", [False] * len(pairs))[k]
        res["pairs"]["%d->%d" % (i, j)] = bool(a and b)
    res["status"] = "PASS" if all(res["pairs"].values()) else "FAIL"
    return res


def child_copy(args):
    import torch
    nbytes = 256 * MiB
    res = {"pairs": {}}
    allok = True
    for i in args.gpus:
        for j in args.gpus:
            if i == j:
                continue
            g = torch.Generator(device="cuda:%d" % i).manual_seed(1234 + i)
            a = torch.randint(-2 ** 31, 2 ** 31 - 1, (nbytes // 4,), dtype=torch.int32,
                              device="cuda:%d" % i, generator=g)
            b = a.to("cuda:%d" % j)
            torch.cuda.synchronize(i)
            torch.cuda.synchronize(j)
            same = torch.equal(a.cpu(), b.cpu())
            # bandwidth: 5 timed copies into a preallocated buffer
            dst = torch.empty_like(b)
            torch.cuda.synchronize(j)
            t0 = time.time()
            for _ in range(5):
                dst.copy_(a, non_blocking=True)
            torch.cuda.synchronize(i)
            torch.cuda.synchronize(j)
            dt = (time.time() - t0) / 5
            res["pairs"]["%d->%d" % (i, j)] = {
                "identical": bool(same),
                "GBps": round(nbytes / dt / 1e9, 2),
                "peer_path": bool(torch.cuda.can_device_access_peer(j, i)),
            }
            allok = allok and same
            del a, b, dst
            torch.cuda.empty_cache()
    res["status"] = "PASS" if allok else "FAIL"
    return res


def _nccl_worker(rank, world, gpus, port, backend, outpath):
    import torch
    import torch.distributed as dist
    from datetime import timedelta
    dev = None
    if backend == "nccl":
        dev = torch.device("cuda:%d" % gpus[rank])
        torch.cuda.set_device(dev)
    else:
        dev = torch.device("cpu")
    dist.init_process_group(backend, init_method="tcp://127.0.0.1:%d" % port,
                            rank=rank, world_size=world, timeout=timedelta(seconds=600))
    rows = []
    expect = world * (world + 1) / 2.0
    for size in NCCL_SIZES:
        n = size // 4
        x = torch.full((n,), float(rank + 1), dtype=torch.float32, device=dev)
        dist.all_reduce(x)  # warm-up (also the first point where hangs show)
        if backend == "nccl":
            torch.cuda.synchronize()
        x.fill_(float(rank + 1))
        dist.barrier()
        t0 = time.time()
        iters = 5
        for _ in range(iters):
            x.fill_(float(rank + 1))
            dist.all_reduce(x)
        if backend == "nccl":
            torch.cuda.synchronize()
        dt = (time.time() - t0) / iters
        ok = bool(torch.all(x == expect).item())
        busbw = 2.0 * (world - 1) / world * size / dt / 1e9
        rows.append({"bytes": size, "correct": ok, "busbw_GBps": round(busbw, 2)})
    if rank == 0:
        with open(outpath, "w") as f:
            json.dump(rows, f)
    dist.barrier()
    dist.destroy_process_group()


def child_nccl(args):
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    world = len(args.gpus)
    port = free_port()
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    procs = [ctx.Process(target=_nccl_worker,
                         args=(r, world, args.gpus, port, args.backend, tmp.name))
             for r in range(world)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    rows = json.loads(read_text(tmp.name) or "[]")
    os.unlink(tmp.name)
    if any(p.exitcode != 0 for p in procs) or not rows:
        return {"status": "ERROR", "detail": "a rank exited with an error (see log)"}
    return {"status": "PASS" if all(r["correct"] for r in rows) else "FAIL", "sizes": rows}


def _vllm_worker(rank, world, gpus, port, use_ca, outpath):
    import torch
    torch.cuda.set_device(gpus[rank])
    from vllm.config import VllmConfig, set_current_vllm_config
    from vllm.distributed.parallel_state import (init_distributed_environment,
                                                 initialize_model_parallel,
                                                 set_custom_all_reduce, get_tp_group)
    from vllm.distributed.communication_op import tensor_model_parallel_all_reduce
    set_custom_all_reduce(use_ca)
    with set_current_vllm_config(VllmConfig()):
        init_distributed_environment(world_size=world, rank=rank,
                                     distributed_init_method="tcp://127.0.0.1:%d" % port,
                                     local_rank=rank, backend="nccl")
        initialize_model_parallel(tensor_model_parallel_size=world)
        comm = get_tp_group().device_communicator
        ca = getattr(comm, "ca_comm", None)
        ca_on = bool(ca is not None and not getattr(ca, "disabled", True))
        rows = []
        expect = world * (world + 1) / 2.0
        for size in [4096, 256 * 1024, 4 * MiB]:
            n = size // 2
            x = torch.full((n,), float(rank + 1), dtype=torch.bfloat16, device="cuda")
            y = tensor_model_parallel_all_reduce(x)
            torch.cuda.synchronize()
            rows.append({"bytes": size, "correct": bool(torch.all(y == expect).item())})
    if rank == 0:
        with open(outpath, "w") as f:
            json.dump({"custom_allreduce_active": ca_on, "sizes": rows}, f)


def child_vllm(args, use_ca):
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    world = len(args.gpus)
    port = free_port()
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    procs = [ctx.Process(target=_vllm_worker, args=(r, world, args.gpus, port, use_ca, tmp.name))
             for r in range(world)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    data = json.loads(read_text(tmp.name) or "{}")
    os.unlink(tmp.name)
    if any(p.exitcode != 0 for p in procs) or not data:
        return {"status": "ERROR", "detail": "vLLM test failed to run (see log; vLLM API may differ)"}
    data["status"] = "PASS" if all(r["correct"] for r in data["sizes"]) else "FAIL"
    return data


def child_main(args):
    stage = args._child
    if stage == "peer":
        res = child_peer(args)
    elif stage == "ipc_small":
        res = child_ipc(args, 1024)
    elif stage == "ipc_large":
        res = child_ipc(args, 64 * MiB)
    elif stage == "copy":
        res = child_copy(args)
    elif stage == "nccl":
        res = child_nccl(args)
    elif stage == "vllm_ca":
        res = child_vllm(args, True)
    elif stage == "vllm_noca":
        res = child_vllm(args, False)
    elif stage == "_sleep":  # used by the self-test of the timeout path
        time.sleep(3600)
        res = {"status": "PASS"}
    else:
        raise SystemExit("unknown stage " + stage)
    with open(args._out, "w") as f:
        json.dump(res, f)


# ---------------------------------------------------------------- verdict


def driver_major(drv):
    m = re.match(r"^(\d+)", drv or "")
    return int(m.group(1)) if m else None


def decide(r):
    """Turn the collected results into (verdict lines, env list, vLLM flags list).

    r keys: world, peer_any, peer_all, ipc_small, ipc_large, copy, nccl_default,
    nccl_p2p_off, nccl_cumem_off, vllm_ca, vllm_noca, iommu_translated, virt,
    container, shm, driver_major, acs_on (each status-like value is a dict with
    'status' or None when not run).
    """
    st = lambda k: (r.get(k) or {}).get("status")
    lines, env, flags = [], [], []

    def add_env(e):
        if e not in env:
            env.append(e)

    def add_flag(f):
        if f not in flags:
            flags.append(f)

    peer = r.get("peer_any")
    world = r.get("world", 2)

    # 1. P2P is reported but the data path is broken
    p2p_broken = peer and (st("ipc_small") in ("FAIL", "HANG", "ERROR")
                           or st("ipc_large") in ("FAIL", "HANG", "ERROR")
                           or st("copy") in ("FAIL", "HANG"))
    if p2p_broken:
        lines.append("CAUSE: the driver reports P2P between these GPUs, but a real "
                     "P2P write or copy failed or hung. vLLM's custom all-reduce and "
                     "NCCL's P2P transport both use this path, so either one can hang.")
        add_flag("--disable-custom-all-reduce")
        add_env("NCCL_P2P_DISABLE=1")
        if r.get("iommu_translated"):
            lines.append("  likely why: the GPUs sit in a translated IOMMU domain (type DMA). "
                         "NVIDIA does not support PCIe P2P with the IOMMU translating on bare "
                         "metal. Fix: boot with iommu=pt (or turn IOMMU / VT-d off in the "
                         "BIOS), then rerun this script.")
        if r.get("acs_on"):
            lines.append("  likely why: ACS is on for a bridge above a GPU (SrcValid+); it "
                         "redirects P2P traffic through the root complex. NCCL's guide says "
                         "to disable ACS on bare metal (BIOS, or setpci).")
        if r.get("virt"):
            lines.append("  likely why: this is a VM (%s). P2P through passthrough needs ACS, "
                         "which VMs keep on; keep the flags below." % r["virt"])
        if st("ipc_small") == "PASS" and st("ipc_large") != "PASS":
            lines.append("  note: the 1 KiB test vLLM uses (VLLM_SKIP_P2P_CHECK=0) passed, so "
                         "vLLM's own check would not catch this; only larger transfers fail.")

    # 2. NCCL results
    nd, no, nc = st("nccl_default"), st("nccl_p2p_off"), st("nccl_cumem_off")
    if nd == "PASS":
        pass
    elif nd is not None:
        if r.get("nccl_default", {}).get("cuda_217") and nc == "PASS":
            lines.append("CAUSE: NCCL fails with 'Cuda failure 217 peer access is not "
                         "supported' and works with NCCL_CUMEM_HOST_ENABLE=0. This is the "
                         "driver bug in NCCL issue #1838, fixed in driver r580 and later.")
            add_env("NCCL_CUMEM_HOST_ENABLE=0")
            dm = r.get("driver_major")
            if dm is not None and dm < 580:
                lines.append("  your driver is %d.x: upgrading to 580 or later removes the "
                             "need for the variable." % dm)
        elif no == "PASS":
            lines.append("CAUSE: NCCL all-reduce %s with default settings and works with "
                         "NCCL_P2P_DISABLE=1, so NCCL's P2P transport is the broken part."
                         % ("hangs" if nd == "HANG" else "fails"))
            add_env("NCCL_P2P_DISABLE=1")
            if peer:
                add_flag("--disable-custom-all-reduce")
        else:
            lines.append("CAUSE: NCCL all-reduce %s even with P2P off. This is below vLLM: "
                         "fix NCCL / driver / container first (see the log tail with "
                         "--verbose)." % ("hangs" if nd == "HANG" else "fails"))
            shm = r.get("shm")
            if shm is not None and shm < 1024 * MiB:
                lines.append("  /dev/shm is only %d MiB. NCCL's SHM transport and vLLM's "
                             "worker queues use it: run the container with --ipc=host, or "
                             "--shm-size=1g --ulimit memlock=-1 as NCCL's docs suggest."
                             % (shm // MiB))

    # 3. vLLM's own all-reduce
    vca, vno = st("vllm_ca"), st("vllm_noca")
    if vca is not None:
        active = (r.get("vllm_ca") or {}).get("custom_allreduce_active")
        if vca != "PASS" and vno == "PASS":
            lines.append("CAUSE: vLLM's tensor-parallel all-reduce %s with custom "
                         "all-reduce on and works with it off." % vca.lower())
            add_flag("--disable-custom-all-reduce")
        elif vca == "PASS" and active is False and not flags:
            lines.append("INFO: vLLM turned custom all-reduce off by itself here (no P2P "
                         "or >2 PCIe GPUs) and uses NCCL.")

    if st("copy") in ("FAIL", "HANG") and not peer:
        lines.append("CAUSE: a GPU-to-GPU copy through host memory %s. With no P2P in "
                     "play this points at the driver, PCIe link or memory, not at vLLM "
                     "flags." % ("hung" if st("copy") == "HANG" else "returned wrong data"))
    if peer and not r.get("peer_all"):
        lines.append("NOTE: the driver reports P2P in one direction only. vLLM ranks may "
                     "then disagree about custom all-reduce; turn it off.")
        add_flag("--disable-custom-all-reduce")

    if not lines:
        if nd == "PASS" and (not peer or (st("ipc_large") == "PASS" and st("copy") == "PASS")):
            lines.append("OK: every check passed. Collectives work; a hang in vLLM is "
                         "likely elsewhere (model load, compilation, a stuck rank). "
                         "Run vLLM with NCCL_DEBUG=INFO and look at the last lines "
                         "before the 60-second warning.")
            if not peer:
                lines.append("  these GPUs have no P2P (normal for GeForce cards): vLLM "
                             "disables custom all-reduce by itself and NCCL uses shared "
                             "memory. --disable-custom-all-reduce only silences the warning.")
            elif world > 2:
                lines.append("  with more than 2 GPUs and no full NVLink, vLLM disables custom "
                             "all-reduce by itself.")
            elif vca is None:
                lines.append("  P2P works, so vLLM will use custom all-reduce. If vLLM still "
                             "hangs at startup, rerun with --vllm to test vLLM's own path.")
        else:
            lines.append("UNSURE: some checks did not run; see the table above.")
    return lines, env, flags


# ---------------------------------------------------------------- main


def fmt_status(d):
    if d is None:
        return "skipped"
    s = d.get("status", "?")
    if d.get("detail") and s != "PASS":
        s += " (" + d["detail"] + ")"
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gpus", default="0,1", help="comma-separated CUDA device indices")
    ap.add_argument("--timeout", type=int, default=60, help="seconds before a check counts as a hang")
    ap.add_argument("--vllm", action="store_true", help="also run vLLM's all-reduce (vLLM must be installed)")
    ap.add_argument("--json", help="write the full report to this file")
    ap.add_argument("--verbose", action="store_true", help="print log tails of failing checks")
    ap.add_argument("--backend", default="nccl", help=argparse.SUPPRESS)  # gloo = CPU self-test
    ap.add_argument("--_child", help=argparse.SUPPRESS)
    ap.add_argument("--_out", help=argparse.SUPPRESS)
    args = ap.parse_args()
    args.gpus = [int(x) for x in args.gpus.split(",") if x.strip() != ""]

    if args._child:
        child_main(args)
        return 0

    if len(set(args.gpus)) < 2 or len(set(args.gpus)) != len(args.gpus):
        print("need at least two different GPUs (--gpus 0,1)")
        return 2

    rep = {"p2pcheck": VERSION, "gpus_tested": args.gpus,
           "time": time.strftime("%Y-%m-%d %H:%M:%S %z")}
    cpu_mode = args.backend != "nccl"
    print("p2pcheck %s  GPUs %s  timeout %ds" % (VERSION, args.gpus, args.timeout))

    # host -----------------------------------------------------------
    gpus = []
    if not cpu_mode:
        rc, out = run_cmd(["nvidia-smi", "--query-gpu=index,name,pci.bus_id,driver_version,compute_cap",
                           "--format=csv,noheader"])
        if rc != 0:
            rc, out = run_cmd(["nvidia-smi", "--query-gpu=index,name,pci.bus_id,driver_version",
                               "--format=csv,noheader"])
        gpus = [g for g in parse_gpu_query(out) if g["index"] in args.gpus]
        if not gpus:
            print("nvidia-smi did not list GPUs %s; is the driver loaded?" % args.gpus)
    rep["gpus"] = gpus
    sids = [pci_sysfs_id(g["bus_id"]) for g in gpus]
    rep["iommu"] = iommu_info(sids)
    rep["acs"] = acs_info(sids)
    rep["virt"] = virt_info()
    rep["shm_bytes"] = shm_bytes()
    rc, topo = run_cmd(["nvidia-smi", "topo", "-m"])
    rc2, p2pr = run_cmd(["nvidia-smi", "topo", "-p2p", "r"])
    rc3, p2pw = run_cmd(["nvidia-smi", "topo", "-p2p", "w"])
    tm, rm, wm = parse_matrix(topo), parse_matrix(p2pr), parse_matrix(p2pw)
    rep["topo"] = {"%d-%d" % k: v for k, v in tm.items()}
    rep["p2p_read"] = {"%d->%d" % k: v for k, v in rm.items()}
    rep["p2p_write"] = {"%d->%d" % k: v for k, v in wm.items()}

    for g in gpus:
        print("  GPU%d %s  bus %s  driver %s  sm %s" % (g["index"], g["name"], g["bus_id"],
                                                       g["driver"], g.get("compute_cap")))
    a, b = args.gpus[0], args.gpus[1]
    print("  link GPU%d-GPU%d: %s   driver P2P read: %s  write: %s" % (
        a, b, tm.get((a, b), "?"), rm.get((a, b), "?"), wm.get((a, b), "?")))
    it = iommu_translated(rep["iommu"])
    print("  IOMMU: %s  kernel args: %s" % (
        {True: "translated (DMA) for a GPU", False: "off or passthrough", None: "unknown"}[it],
        " ".join(rep["iommu"]["cmdline"]) or "none"))
    acs_on = [k for k, v in rep["acs"].items() if v == "on"]
    acs_unknown = [k for k, v in rep["acs"].items() if v.startswith("unknown")]
    print("  ACS on bridges above GPUs: %s" % (
        ", ".join(acs_on) if acs_on else ("unknown (run as root)" if acs_unknown else "off/none")))
    v = rep["virt"]
    print("  VM: %s  WSL: %s  container: %s  /dev/shm: %s MiB" % (
        v["hypervisor"] or "no", "yes" if v["wsl"] else "no", v["container"] or "no",
        (rep["shm_bytes"] or 0) // MiB))

    # children -------------------------------------------------------
    results = {}

    def stage(name, label, extra_env=None):
        print("  %-38s" % label, end="", flush=True)
        res = run_child(name if not name.startswith("nccl") else "nccl", args, extra_env, args.timeout)
        results[name] = res
        msg = fmt_status(res)
        if name.startswith("nccl") and res.get("transports"):
            msg += "  via " + ", ".join(res["transports"])
        if name.startswith("nccl") and res.get("sizes"):
            msg += "  busbw@64MiB %.1f GB/s" % res["sizes"][-1]["busbw_GBps"]
        if name == "copy" and res.get("pairs"):
            msg += "  " + "  ".join("%s %s GB/s" % (k, p["GBps"]) for k, p in res["pairs"].items())
        print(msg)
        if args.verbose and res.get("status") != "PASS":
            print("    --- log tail ---\n    " + res.get("log_tail", "").replace("\n", "\n    "))
        return res

    print("checks:")
    peer_any = peer_all = False
    if not cpu_mode:
        pr = stage("peer", "peer report (can_device_access_peer)")
        if pr.get("status") != "PASS":
            tail = [l for l in pr.get("log_tail", "").splitlines() if l.strip()]
            print("\nPyTorch could not use GPUs %s, so nothing else can be tested.\n  %s"
                  % (args.gpus, tail[-1] if tail else ""))
            print("Run this in the environment that runs vLLM, with the GPUs visible.")
            if args.json:
                rep["checks"] = results
                with open(args.json, "w") as f:
                    json.dump(rep, f, indent=1, default=str)
            return 1
        if pr.get("status") == "PASS":
            vals = list(pr.get("peer", {}).values())
            peer_any, peer_all = any(vals), all(vals)
            print("    torch %s  CUDA %s  NCCL %s  vLLM %s  peer: %s" % (
                pr.get("torch"), pr.get("torch_cuda"), pr.get("nccl"), pr.get("vllm"),
                ", ".join("%s=%s" % (k, "yes" if x else "no") for k, x in pr["peer"].items())))
        if peer_any:
            stage("ipc_small", "P2P IPC write, 1 KiB (vLLM's test)")
            stage("ipc_large", "P2P IPC write, 64 MiB")
        else:
            print("  %-38s skipped (driver reports no P2P)" % "P2P IPC write")
        stage("copy", "GPU-to-GPU copy 256 MiB, verified")
    nccl_env = {"NCCL_DEBUG": "INFO", "NCCL_DEBUG_SUBSYS": "INIT"}
    stage("nccl_default", "all-reduce, NCCL defaults", nccl_env)
    stage("nccl_p2p_off", "all-reduce, NCCL_P2P_DISABLE=1", dict(nccl_env, NCCL_P2P_DISABLE="1"))
    if results["nccl_default"].get("status") != "PASS":
        stage("nccl_cumem_off", "all-reduce, NCCL_CUMEM_HOST_ENABLE=0",
              dict(nccl_env, NCCL_CUMEM_HOST_ENABLE="0"))
    if args.vllm and not cpu_mode:
        stage("vllm_ca", "vLLM all-reduce, custom all-reduce on")
        stage("vllm_noca", "vLLM all-reduce, custom all-reduce off")

    rep["checks"] = results
    drv = gpus[0]["driver"] if gpus else None
    r = dict(results)
    r.update({"world": len(args.gpus), "peer_any": peer_any, "peer_all": peer_all,
              "iommu_translated": it, "virt": v["hypervisor"] or ("WSL" if v["wsl"] else None),
              "container": v["container"], "shm": rep["shm_bytes"],
              "driver_major": driver_major(drv), "acs_on": bool(acs_on)})
    lines, env, flags = decide(r)
    rep["verdict"] = {"lines": lines, "env": env, "vllm_flags": flags}
    print("\nverdict:")
    for l in lines:
        print("  " + l)
    cmd = " ".join(env + ["vllm serve <model> --tensor-parallel-size %d" % len(args.gpus)] + flags)
    print("\nrun vLLM as:\n  " + cmd)
    rep["verdict"]["command"] = cmd
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rep, f, indent=1, default=str)
        print("\nfull report: " + args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
