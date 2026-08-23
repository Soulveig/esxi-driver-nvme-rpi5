# v1.1.0

## English

- Adds a one-branch lost-wakeup fix to build-24449057 `vmknvme`.
- Checks raw-command pending state before the first wait when the transport has
  already completed inline.
- Reduces validated `nvmeBusDriver` attachment from 70,456 ms to 429 ms and
  external reachability from about 66 seconds to 26 seconds.

## Русский

- Добавлено исправление одной ветки для lost wakeup в `vmknvme` сборки
  24449057.
- Pending-state raw-команды проверяется до первого ожидания, если транспорт уже
  завершил команду синхронно.
- Проверенное время `nvmeBusDriver attachDevice` снижено с 70 456 до 429 мс,
  внешняя доступность — примерно с 66 до 26 секунд.
