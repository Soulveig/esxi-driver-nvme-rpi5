# v1.1.0

## English

- Adds a one-branch lost-wakeup fix to build-24449057 `vmknvme`.
- Checks raw-command pending state before the first wait when the transport has
  already completed inline.
- Reduces validated `nvmeBusDriver` attachment from 70,456 ms to 429 ms and
  external reachability from about 66 seconds to 26 seconds.
- Keeps the v1.0.0 `nvme_pcie` transport payload byte-for-byte unchanged.
- Packages the fix as a byte-preserving `native-misc-drivers` replacement so
  the patched module loads in the original `native_m.v00` position.
- Keeps single CQ ownership; no timeout shortening or extra polling is added.

## Русский

- Добавлено исправление одной ветки для lost wakeup в `vmknvme` сборки
  24449057.
- Pending-state raw-команды проверяется до первого ожидания, если транспорт уже
  завершил команду синхронно.
- Проверенное время `nvmeBusDriver attachDevice` снижено с 70 456 до 429 мс,
  внешняя доступность — примерно с 66 до 26 секунд.
- Payload транспорта `nvme_pcie` из v1.0.0 сохранён byte-for-byte.
- Исправление упаковано как byte-preserving replacement
  `native-misc-drivers`, поэтому модуль загружается в исходной позиции
  `native_m.v00`.
- Сохраняется единственный владелец CQ; таймауты не сокращаются, дополнительный
  polling не добавлен.
