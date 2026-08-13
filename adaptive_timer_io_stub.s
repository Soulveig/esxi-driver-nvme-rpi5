.text
.p2align 2
.global adaptive_timer_io_stub
adaptive_timer_io_stub:
    stp x19, x20, [sp, #-64]!
    stp x21, x22, [sp, #16]
    stp x23, x24, [sp, #32]
    stp x25, x30, [sp, #48]
    mov x22, x0
    ldr w21, [x22, #0x40]
    cbz w21, done
    mov w25, #8

round:
    mov w24, #0
    ldr x20, [x22, #0xb8]
    add x20, x20, #80
    mov w19, #1
queue:
    ldr w0, [x20, #4]
    cmp w0, #2
    b.ne next
    ldr x0, [x20, #0x20]
    ldr x0, [x0]
    bl vmk_SpinlockLock
    mov x0, x20
    bl NVMEPCIEProcessCq
    add w24, w24, w0
    ldr x0, [x20, #0x20]
    ldr x0, [x0]
    bl vmk_SpinlockUnlock
next:
    add x20, x20, #80
    add w19, w19, #1
    cmp w19, w21
    b.ls queue
    cbz w24, done
    subs w25, w25, #1
    b.ne round

done:
    ldp x25, x30, [sp, #48]
    ldp x23, x24, [sp, #32]
    ldp x21, x22, [sp, #16]
    ldp x19, x20, [sp], #64
    ret
