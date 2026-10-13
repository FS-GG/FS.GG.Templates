#![no_std]
use core::panic::PanicInfo;
use fsgg_wasm_guest::{allocate, free_last, write_descriptor, SC2_ABI_VERSION};

#[panic_handler]
fn panic(_: &PanicInfo) -> ! { loop {} }
#[repr(align(4))]
struct Storage([u8; 65536]);
static mut STORAGE: Storage = Storage([0; 65536]);
static mut NEXT: usize = 0;
static mut OUTPUT: [u8; 3] = [b'P', 1, 0];

#[no_mangle]
pub extern "C" fn sc2c_abi_version() -> u32 { SC2_ABI_VERSION }
#[no_mangle]
pub extern "C" fn sc2c_alloc(length: u32) -> u32 {
    unsafe { allocate(core::ptr::addr_of_mut!(STORAGE.0).cast(), 65536, core::ptr::addr_of_mut!(NEXT), length) }
}
#[no_mangle]
pub extern "C" fn sc2c_free(pointer: u32, length: u32) {
    unsafe { free_last(core::ptr::addr_of_mut!(STORAGE.0).cast(), core::ptr::addr_of_mut!(NEXT), pointer, length) }
}
#[no_mangle]
pub extern "C" fn sc2c_initialize(pointer: u32, length: u32, descriptor: u32) -> i32 {
    if pointer == 0 || length == 0 || descriptor == 0 { return 2; }
    write_descriptor(descriptor, core::ptr::addr_of!(OUTPUT).cast::<u8>() as u32, 3);
    0
}
#[no_mangle]
pub extern "C" fn sc2c_process(pointer: u32, length: u32, descriptor: u32) -> i32 {
    if pointer == 0 || length != 2 || descriptor == 0 { return 2; }
    let input = unsafe { core::slice::from_raw_parts(pointer as *const u8, 2) };
    if input[0] != 1 || input[1] > 2 { return 2; }
    unsafe { OUTPUT[2] = input[1]; }
    write_descriptor(descriptor, core::ptr::addr_of!(OUTPUT).cast::<u8>() as u32, 3);
    0
}
#[no_mangle]
pub extern "C" fn sc2c_shutdown() -> i32 { unsafe { NEXT = 0; } 0 }
