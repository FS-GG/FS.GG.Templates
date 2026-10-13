#include "fsgg-wasm-guest.h"

static uint8_t storage[65536] __attribute__((aligned(4)));
static fsgg_wasm_arena arena = { storage, sizeof(storage), 0 };
static uint8_t output[3] = { 'P', 1, 0 };

uint32_t sc2c_abi_version(void) { return FSGG_WASM_SC2_ABI_VERSION; }
uint32_t sc2c_alloc(uint32_t length) { return fsgg_wasm_allocate(&arena, length); }
void sc2c_free(uint32_t pointer, uint32_t length) { fsgg_wasm_free_last(&arena, pointer, length); }
int32_t sc2c_initialize(uint32_t pointer, uint32_t length, uint32_t descriptor) {
    if (!pointer || !length || !descriptor) return 2;
    fsgg_wasm_write_descriptor(descriptor, (uint32_t)(uintptr_t)output, sizeof(output));
    return 0;
}
int32_t sc2c_process(uint32_t pointer, uint32_t length, uint32_t descriptor) {
#if defined(POLICY_TRAP)
    __builtin_trap();
#elif defined(POLICY_LOOP)
    for (;;) { __asm__ volatile(""); }
#endif
    if (!pointer || length != 2 || !descriptor) return 2;
    const uint8_t *input = (const uint8_t *)(uintptr_t)pointer;
    if (input[0] != 1 || input[1] > 2) return 2;
    output[2] = input[1];
#if defined(POLICY_MALFORMED)
    output[0] = 'X';
#endif
    fsgg_wasm_write_descriptor(descriptor, (uint32_t)(uintptr_t)output, sizeof(output));
    return 0;
}
int32_t sc2c_shutdown(void) { arena.next = 0; return 0; }
