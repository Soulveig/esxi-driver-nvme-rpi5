.text
.p2align 2
.global hybrid_inline_admin_stub
hybrid_inline_admin_stub:
    stp x19, x20, [sp, #-32]!
    str x30, [sp, #16]
    mov x19, x3
    ldr w0, [x19]
    cbnz w0, 2f
    mov w20, #0x4240
    movk w20, #0xf, lsl #16
1:
    mov x0, x19
    bl NVMEPCIEProcessCq
    cbnz w0, 2f
    subs w20, w20, #1
    b.ne 1b
2:
    add x3, x19, #8
    mov w0, #0
    ldr x30, [sp, #16]
    ldp x19, x20, [sp], #32
    ret
