.text
.p2align 2
.global hybrid_timer_io_stub
hybrid_timer_io_stub:
    stp x19, x20, [sp, #-48]!
    stp x21, x22, [sp, #16]
    str x30, [sp, #32]
    ldr x20, [x0, #0xb8]
    ldr w21, [x0, #0x40]
    cbz w21, 3f
    add x20, x20, #80
    mov w19, #1
1:
    ldr w0, [x20, #4]
    cmp w0, #2
    b.ne 2f
    ldr x0, [x20, #0x20]
    ldr x0, [x0]
    bl vmk_SpinlockLock
    mov x0, x20
    bl NVMEPCIEProcessCq
    ldr x0, [x20, #0x20]
    ldr x0, [x0]
    bl vmk_SpinlockUnlock
2:
    add x20, x20, #80
    add w19, w19, #1
    cmp w19, w21
    b.ls 1b
3:
    ldr x30, [sp, #32]
    ldp x21, x22, [sp, #16]
    ldp x19, x20, [sp], #48
    ret
