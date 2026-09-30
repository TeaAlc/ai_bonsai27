/* Query CUDA device 0 without CUDA headers, a toolkit, or nvidia-smi.
 * The host/container GPU runtime must supply the CUDA driver library.
 * Driver API attribute IDs 75/76 are the public major/minor capability IDs.
 */
#include <dlfcn.h>
#include <stdio.h>

int main(void) {
    void *driver = dlopen("libcuda.so.1", RTLD_NOW | RTLD_LOCAL);
    if (!driver) {
        fprintf(stderr, "CUDA detection: cannot load libcuda.so.1: %s\n", dlerror());
        return 2;
    }
    int (*initialize)(unsigned int) = (int (*)(unsigned int))dlsym(driver, "cuInit");
    int (*get_device)(int *, int) = (int (*)(int *, int))dlsym(driver, "cuDeviceGet");
    int (*get_attribute)(int *, int, int) = (int (*)(int *, int, int))dlsym(driver, "cuDeviceGetAttribute");
    if (!initialize || !get_device || !get_attribute) {
        fprintf(stderr, "CUDA detection: required driver symbols are missing.\n");
        dlclose(driver);
        return 2;
    }
    int device, major, minor;
    int result = initialize(0);
    if (result == 0) result = get_device(&device, 0);
    if (result == 0) result = get_attribute(&major, 75, device);
    if (result == 0) result = get_attribute(&minor, 76, device);
    if (result != 0) {
        fprintf(stderr, "CUDA detection: driver query failed (CUDA error %d). Check GPU passthrough.\n", result);
        dlclose(driver);
        return 2;
    }
    printf("%d.%d\n", major, minor);
    dlclose(driver);
    return 0;
}
