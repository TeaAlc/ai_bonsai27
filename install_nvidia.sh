#!/usr/bin/env bash
# Native Linux NVIDIA driver + rootless Podman CDI setup and diagnostics.
set -euo pipefail
script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$script_directory/data/logging.sh"
bonsai_init_logging nvidia-setup

usage() {
    cat <<'HELP'
Usage: install_nvidia.sh [--check|--repair-cdi|--driver-only|--toolkit-only]
                         [--verify-container] [--image IMAGE] [--log PATH]
Default: keep a working driver; install a missing distro driver, Podman,
         and NVIDIA Container Toolkit/CDI on Linux Mint, Ubuntu, or Debian.
--check           Diagnose without package/configuration changes (logs are saved).
--repair-cdi      Regenerate installed CDI support without package downloads.
--verify-container Require a successful CUDA probe in a cached project image.
--image IMAGE     Select the CUDA-probe image and require container verification.
--log PATH        Save stdout/stderr; default: results/nvidia-setup/<UTC>-<PID>.log.
Installation needs sudo/root; run as your normal user for rootless Podman tests.
No reboot, model download, image pull, or host CUDA development-kit installation.
Exit 3: driver installation completed; reboot and rerun before configuring CDI.
HELP
}
fail() { bonsai_log ERROR "$*"; exit 1; }
mode=install
mode_selected=false
verify_container=false
image=${BONSAI_IMAGE:-localhost/bonsai2-27b:latest}
log_path=''
while (( $# )); do
    case "$1" in
        --check|--repair-cdi|--driver-only|--toolkit-only)
            "$mode_selected" && fail 'Select only one setup mode.'
            mode_selected=true
            case "$1" in
                --check) mode=check ;;
                --repair-cdi) mode=repair ;;
                --driver-only) mode=driver ;;
                --toolkit-only) mode=toolkit ;;
            esac ;;
        --verify-container) verify_container=true ;;
        --image|--log)
            (( $# >= 2 )) && [[ -n "$2" ]] || fail "Missing value for $1."
            if [[ "$1" == --image ]]; then image=$2; verify_container=true; else log_path=$2; fi
            shift ;;
        --help|-h) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
    shift
done

# Log only selected diagnostics, never the full environment or command text.
umask 077
log_path=${log_path:-$script_directory/results/nvidia-setup/$(date -u +%Y%m%dT%H%M%SZ)-$$.log}
mkdir -p -- "$(dirname -- "$log_path")"
[[ ! -e "$log_path" ]] || fail 'Log path already exists; select a new file.'
: > "$log_path"
exec > >(tee -a -- "$log_path") 2>&1
bonsai_step diagnostics "Mode=$mode; log=$log_path"
if [[ -e /dev/dxg ]] || grep -qi microsoft /proc/sys/kernel/osrelease; then
    fail 'WSL uses the Windows NVIDIA driver and /dev/dxg. Use ./run.sh there; do not install a Linux driver.'
fi
source /etc/os-release
case "${ID:-}" in linuxmint|ubuntu|debian) ;; *) fail 'Supported distributions: Linux Mint, Ubuntu, Debian.' ;; esac
bonsai_log INFO "OS=${PRETTY_NAME:-$ID}; architecture=$(uname -m); kernel=$(uname -r); user=$(id -un); uid=$EUID"
bonsai_log INFO "Selected image=$image; host CUDA development toolkit is not required."
for diagnostic in lspci mokutil modinfo dpkg-query systemctl; do
    command -v "$diagnostic" >/dev/null || bonsai_log WARN "Optional diagnostic unavailable: $diagnostic"
done
if command -v lspci >/dev/null; then lspci -nn -d 10de: || true; fi
if command -v mokutil >/dev/null; then mokutil --sb-state || true; fi
if command -v modinfo >/dev/null; then modinfo -F version nvidia || true; fi
if [[ -r /proc/driver/nvidia/version ]]; then cat /proc/driver/nvidia/version; fi
if command -v dpkg-query >/dev/null; then
    dpkg-query -W -f='${binary:Package} ${Version} ${db:Status-Abbrev}\n' \
        'nvidia-driver*' 'nvidia-container*' 'libnvidia-container*' 'cuda-toolkit*' nvidia-cuda-toolkit podman 2>/dev/null || true
fi
# Record engine/toolkit/service details even when the driver or CDI check fails.
for diagnostic in podman nvidia-ctk crun runc nvcc; do
    if command -v "$diagnostic" >/dev/null; then
        bonsai_log INFO "Diagnostic tool=$diagnostic"
        "$diagnostic" --version || true
    fi
done
if command -v systemctl >/dev/null; then
    systemctl --no-pager status nvidia-cdi-refresh.path nvidia-cdi-refresh.service || true
    if command -v journalctl >/dev/null; then
        journalctl --no-pager -u nvidia-cdi-refresh.service -n 30 2>/dev/null || true
    fi
fi
bonsai_log INFO 'The CUDA version shown by nvidia-smi is the driver-supported level, not proof of an installed host CUDA SDK.'
if [[ -f /var/run/reboot-required ]]; then bonsai_log WARN 'The system reports a pending reboot.'; fi

privileged=()
installer_directory=''
cleanup() { [[ -z "$installer_directory" ]] || rm -rf -- "$installer_directory"; }
trap cleanup EXIT
prepare_privileges() {
    if (( EUID != 0 )); then
        command -v sudo >/dev/null || fail 'Installation requires sudo or root; --check needs neither.'
        privileged=(sudo)
        sudo -v
    fi
    local temporary_root=${TMPDIR:-/tmp/bonsai27}
    mkdir -p "$temporary_root"
    installer_directory=$(mktemp -d "$temporary_root/nvidia-setup.XXXXXXXX")
}
host_driver_works() { command -v nvidia-smi >/dev/null && nvidia-smi; }
install_driver() {
    bonsai_step driver 'Installing the distribution driver; preserve APT confirmation prompts.'
    "${privileged[@]}" apt-get update
    "${privileged[@]}" apt-get install --no-install-recommends pciutils "linux-headers-$(uname -r)"
    local driver_package driver_info gpu_info
    gpu_info=$(lspci -nn -d 10de:)
    [[ "$gpu_info" =~ (VGA|3D|Display) ]] || fail 'No NVIDIA display GPU detected; no driver will be installed.'
    local -a recommended_packages=()
    if [[ "$ID" == debian ]]; then
        driver_package=nvidia-driver
        bonsai_log INFO 'Debian needs contrib/non-free/non-free-firmware enabled by the administrator; sources are not rewritten.'
    else
        "${privileged[@]}" apt-get install --no-install-recommends ubuntu-drivers-common
        driver_info=$(ubuntu-drivers devices)
        printf '%s\n' "$driver_info"
        mapfile -t recommended_packages < <(printf '%s\n' "$driver_info" |
            awk '$1 == "driver" && $2 == ":" && $NF == "recommended" {print $3}' | sort -u)
        (( ${#recommended_packages[@]} == 1 )) || fail 'Expected one recommended driver; review the distribution Driver Manager.'
        driver_package=${recommended_packages[0]}
        [[ "$driver_package" =~ ^nvidia-driver-[0-9]+(-open|-server|-server-open)?$ ]] || fail 'Unexpected driver package name.'
    fi
    bonsai_log INFO "Selected driver package=$driver_package"
    "${privileged[@]}" apt-get install "$driver_package"
    bonsai_log WARN 'Reboot, complete Secure Boot/MOK enrollment if requested, then rerun this script. No reboot was performed.'
    exit 3
}
check_cdi() {
    command -v nvidia-ctk >/dev/null || fail 'NVIDIA Container Toolkit is missing.'
    nvidia-ctk --version
    local devices podman_version
    devices=$(nvidia-ctk cdi list)
    printf '%s\n' "$devices"
    [[ "$devices" == *'nvidia.com/gpu=all'* ]] || fail 'CDI GPU selector missing; install or run --repair-cdi.'
    podman_version=$(podman --version)
    if [[ "$podman_version" == 'podman version 4.'* ]] &&
        grep -q 'additionalGids:' /etc/cdi/*.yaml /var/run/cdi/*.yaml 2>/dev/null; then
        fail 'Podman 4 cannot parse additionalGids; run --repair-cdi or upgrade Podman.'
    fi
    if [[ -f /etc/cdi/nvidia.yaml && -f /var/run/cdi/nvidia.yaml ]]; then
        fail 'Duplicate NVIDIA CDI specifications in /etc/cdi and /var/run/cdi; resolve before startup.'
    fi
    for specification in /etc/cdi/*.yaml /var/run/cdi/*.yaml; do
        [[ -f "$specification" ]] || continue
        bonsai_log INFO "CDI specification=$specification"
        stat -c 'mode=%a owner=%U:%G size=%s modified=%y' "$specification"
        sha256sum "$specification"
        sed -n '1,6p' "$specification"
    done
}
verify_runtime() {
    bonsai_step verification 'Checking Podman and container CUDA access.'
    command -v podman >/dev/null || fail 'Podman is missing.'
    podman --version
    # Select fields rather than dumping registry credentials or every setting.
    podman info --format 'rootless={{.Host.Security.Rootless}} runtime={{.Host.OCIRuntime.Name}} cgroup={{.Host.CgroupsVersion}}'
    local image_status=0
    podman image exists "$image" || image_status=$?
    if (( image_status > 1 )); then fail "Podman image lookup failed (exit=$image_status)."; fi
    if (( image_status == 1 )); then
        if "$verify_container"; then fail 'Probe image is not cached. Pull/build the project image, then rerun --check --verify-container.'; fi
        bonsai_log WARN 'No cached project image: host/CDI checks only; container CUDA remains unverified.'
        return
    fi
    podman image inspect --format 'image={{.Id}} source={{index .Labels "org.opencontainers.image.revision"}} version={{index .Labels "org.opencontainers.image.version"}}' "$image"
    # No model mounts, API ports, downloads, or interference with the running LLM.
    local capability
    capability=$(podman run --rm --pull=never --network none --device nvidia.com/gpu=all \
        --security-opt label=disable --env NVIDIA_DRIVER_CAPABILITIES=compute,utility \
        --entrypoint /opt/bonsai/cuda-compute-capability "$image")
    bonsai_log INFO "Actual container CUDA device 0 compute capability=$capability"
    case "$capability" in 8.6|8.9|12.0) ;; *) fail 'Unsupported GPU capability for the project image.' ;; esac
    podman run --rm --pull=never --network none --device nvidia.com/gpu=all \
        --security-opt label=disable --env NVIDIA_DRIVER_CAPABILITIES=compute,utility \
        --entrypoint bash "$image" /opt/bonsai/check-runtime.sh
    bonsai_log INFO 'Container CUDA driver access and runtime dependencies passed.'
}

bonsai_step driver 'Checking the active NVIDIA driver.'
if ! host_driver_works; then
    case "$mode" in
        install|driver) prepare_privileges; install_driver ;;
        *) fail 'Host driver unavailable. Run the default installer, reboot if requested, and inspect Secure Boot/kernel diagnostics.' ;;
    esac
fi
bonsai_log INFO 'Host driver works; it will not be replaced.'
nvidia-smi --query-gpu=index,name,uuid,pci.bus_id,driver_version,memory.total,memory.used,compute_cap --format=csv ||
    bonsai_log WARN 'Extended GPU query failed; inspect the preceding driver output.'
if (( EUID == 0 )); then bonsai_log WARN 'Running as root: Podman verification uses root storage, not your rootless user storage.'; fi
if [[ "$mode" == driver ]]; then exit 0; fi
if [[ "$mode" == check ]]; then
    command -v podman >/dev/null || fail 'Podman is missing.'
    check_cdi
    verify_runtime
    bonsai_log INFO 'Diagnosis complete; no host packages/configuration changed.'
    exit 0
fi
prepare_privileges
if [[ "$mode" != repair ]] && ! command -v podman >/dev/null; then
    "${privileged[@]}" apt-get update
    "${privileged[@]}" apt-get install --no-install-recommends podman
fi
command -v podman >/dev/null || fail 'Podman is missing; install it before --repair-cdi.'
# Use NVIDIA's signed production APT repository, scoped to its own keyring.
bonsai_step toolkit "Installing or refreshing NVIDIA Container Toolkit/CDI."
if [[ "$mode" != repair ]]; then
    "${privileged[@]}" apt-get update
    "${privileged[@]}" apt-get install --no-install-recommends ca-certificates curl gnupg
    curl --connect-timeout 30 --max-time 300 --fail --show-error --silent --location --proto '=https' --proto-redir '=https' \
        https://nvidia.github.io/libnvidia-container/gpgkey \
        --output "$installer_directory/key.asc"
    gpg --batch --dearmor --output "$installer_directory/key.gpg" "$installer_directory/key.asc"
    curl --connect-timeout 30 --max-time 300 --fail --show-error --silent --location --proto '=https' --proto-redir '=https' \
        https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
        --output "$installer_directory/repository.list"
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
        "$installer_directory/repository.list" > "$installer_directory/signed-repository.list"
    bonsai_log INFO "NVIDIA repository/key identities:"
    sha256sum "$installer_directory/key.gpg" "$installer_directory/signed-repository.list"
    "${privileged[@]}" install -m 0644 "$installer_directory/key.gpg" \
        /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    "${privileged[@]}" install -m 0644 "$installer_directory/signed-repository.list" \
        /etc/apt/sources.list.d/nvidia-container-toolkit.list
    "${privileged[@]}" apt-get update

    # Native Podman CDI only needs the base package (CLI and CDI hooks).
    # Keep APT's package summary and confirmation visible.
    "${privileged[@]}" apt-get install nvidia-container-toolkit-base
fi
command -v nvidia-ctk >/dev/null || fail 'Install the toolkit first by running without --repair-cdi.'

bonsai_step cdi "Generating a driver-matched CDI specification."
# Podman 4 ships an older CDI parser. Use NVIDIA's supported generation flag,
# and persist it for the refresh service so a reboot does not undo the repair.
generation_arguments=()
podman_version=$(podman --version)
if [[ "$podman_version" == 'podman version 4.'* ]]; then
    generation_arguments+=(--feature-flag no-additional-gids-for-device-nodes)
    refresh_environment=/etc/nvidia-container-toolkit/nvidia-cdi-refresh.env
    if [[ -f "$refresh_environment" ]]; then
        cp "$refresh_environment" "$installer_directory/refresh.env"
        if grep -q '^NVIDIA_CTK_CDI_GENERATE_FEATURE_FLAGS=' "$installer_directory/refresh.env"; then
            grep -q '^NVIDIA_CTK_CDI_GENERATE_FEATURE_FLAGS=no-additional-gids-for-device-nodes$' "$installer_directory/refresh.env" ||
                fail 'Existing CDI feature flags need manual review before adding no-additional-gids-for-device-nodes.'
        else
            printf '\nNVIDIA_CTK_CDI_GENERATE_FEATURE_FLAGS=no-additional-gids-for-device-nodes\n' >> "$installer_directory/refresh.env"
        fi
    else
        printf 'NVIDIA_CTK_CDI_GENERATE_FEATURE_FLAGS=no-additional-gids-for-device-nodes\n' > "$installer_directory/refresh.env"
    fi
    "${privileged[@]}" mkdir -p /etc/nvidia-container-toolkit
    "${privileged[@]}" install -m 0644 "$installer_directory/refresh.env" "$refresh_environment"
fi
# Reuse the automatic refresh service's path if it already generated a spec,
# avoiding duplicate NVIDIA device definitions in the two CDI search paths.
cdi_path=/etc/cdi/nvidia.yaml
if [[ -f /var/run/cdi/nvidia.yaml ]]; then
    [[ ! -f /etc/cdi/nvidia.yaml ]] || fail 'NVIDIA specifications exist in both /etc/cdi and /var/run/cdi; resolve duplicate definitions first.'
    cdi_path=/var/run/cdi/nvidia.yaml
fi
"${privileged[@]}" mkdir -p "${cdi_path%/*}"
"${privileged[@]}" nvidia-ctk cdi generate "${generation_arguments[@]}" --output="$installer_directory/nvidia.yaml"
# Publish only a successfully generated specification; preserve a prior copy.
if [[ -f "$cdi_path" ]]; then
    "${privileged[@]}" cp -p "$cdi_path" "$cdi_path.bak"
fi
"${privileged[@]}" install -m 0644 "$installer_directory/nvidia.yaml" "$cdi_path"
cdi_devices=$(nvidia-ctk cdi list)
printf '%s\n' "$cdi_devices"
[[ "$cdi_devices" == *'nvidia.com/gpu=all'* ]] || fail 'Installation completed but the NVIDIA CDI GPU selector is missing.'
bonsai_log INFO 'CDI configured. Start the project as your normal user with ./run.sh.'
bonsai_log INFO 'After driver or GPU changes, rerun with --repair-cdi.'

check_cdi
verify_runtime
bonsai_step complete 'NVIDIA host/container setup completed; diagnostics saved in the log.'
