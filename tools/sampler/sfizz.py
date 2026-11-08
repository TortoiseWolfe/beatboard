"""Command builders for sfizz_render 1.2.3 (the standard command-line SFZ sampler), run in the beatboard-sfizz container.

Only flags the 1.2.3 binary really has are used: --sfz --midi --wav --samplerate --quality --polyphony --use-eot.
(There is no --oversampling flag; an earlier helper used one and could never have run.)

sfizz_render is not on the host. The container is built from tools/sampler/Dockerfile and every call goes through
~/.claude/scripts/docker-heavy.sh, which queues heavy jobs one at a time and enforces a timeout.
"""
import os
import subprocess

IMAGE = "beatboard-sfizz"
HEAVY = os.path.expanduser("~/.claude/scripts/docker-heavy.sh")


def render_args(sfz, midi, wav, rate=48000, quality=3, polyphony=64, use_eot=True):
    """The sfizz_render command line itself (paths as the program will see them)."""
    cmd = ["sfizz_render", "--sfz", sfz, "--midi", midi, "--wav", wav,
           "--samplerate", str(rate), "--quality", str(quality), "--polyphony", str(polyphony)]
    if use_eot:
        cmd.append("--use-eot")
    return cmd


def container_command(inner, mounts, tag, timeout=900, mem="6g", cpus=4, image=IMAGE, heavy=HEAVY):
    """Wrap a command in docker-heavy.sh + docker run. `mounts` is [(host_dir, container_dir, 'ro'|'rw')].

    The container has no network. Host files keep the caller's user id so the outputs are ours.
    """
    cmd = [heavy, "--mem", mem, "--cpus", str(cpus), "--timeout", str(timeout), "--tag", tag, "--",
           "docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}"]
    for host, inside, mode in mounts:
        cmd += ["-v", f"{host}:{inside}:{mode}"]
    return cmd + [image] + list(inner)


def run(cmd, timeout=None):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"{cmd[0]} exited {r.returncode}: {(r.stderr or r.stdout)[-600:]}")
    return r
