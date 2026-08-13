.text
.p2align 2
.global hybrid_admin_oneshot_io_stub
hybrid_admin_oneshot_io_stub:
    stp x19, x20, [sp, #-32]!
    str x30, [sp, #16]
    mov x19, x3
    ldr w0, [x19]
    cbz w0, admin_poll

    // IO queue: one serialized CQ pass, then return immediately.  The normal
    // controller timer remains the fallback when the CQE is not ready yet.
    ldr x0, [x19, #0x20]
    ldr x0, [x0]
    bl vmk_SpinlockLock
    mov x0, x19
    bl NVMEPCIEProcessCq
    ldr x0, [x19, #0x20]
    ldr x0, [x0]
    bl vmk_SpinlockUnlock
    b done

admin_poll:
    mov w20, #0x4240
    movk w20, #0x000f, lsl #16
1:
    mov x0, x19
    bl NVMEPCIEProcessCq
    cbnz w0, done
    subs w20, w20, #1
    b.ne 1b

done:
    add x3, x19, #8
    mov w0, #0
    ldr x30, [sp, #16]
    ldp x19, x20, [sp], #32
    ret
