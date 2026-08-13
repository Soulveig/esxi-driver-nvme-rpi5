# v1.0.0

## English

- First release of the Raspberry Pi 5 completion-path adaptation for the stock
  ESXi-Arm `nvme_pcie` transport.
- Adds bounded admin CQ processing, one post-submission IO CQ pass, and up to
  eight productive lifecycle-timer passes.
- Uses the VMKNVME completion world; installation instructions set
  `vmknvme_compl_world_type=1`.
- Targets only ESXi-Arm 8.0U3c build 24449057.
- Requires BootBankInstaller, disabled Secure Boot, and a reboot.

## Русский

- Первый релиз адаптации completion path штатного транспорта ESXi-Arm
  `nvme_pcie` для Raspberry Pi 5.
- Добавлены ограниченная обработка admin CQ, один проход IO CQ после отправки и
  до восьми продуктивных проходов lifecycle timer.
- Используется VMKNVME completion world; инструкция задаёт
  `vmknvme_compl_world_type=1`.
- Поддерживается только ESXi-Arm 8.0U3c build 24449057.
- Требуются BootBankInstaller, отключённый Secure Boot и перезагрузка.
