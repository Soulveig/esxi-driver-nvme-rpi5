# Raspberry Pi 5 NVMe adaptation for ESXi-Arm v1.1.0

**[English](#english) | [Русский](#русский)**

> **Build-specific CommunitySupported package.** Use only with ESXi-Arm
> 8.0U3c build 24449057. Disable Secure Boot and preserve physical console
> access plus a known-good alternate bootbank.

## English

### What changed

Version 1.1.0 fixes a startup lost wakeup in `vmknvme`. The
transport can complete an early raw admin command before
`NVMEExecuteRawCommand` starts waiting. Stock code skipped its existing
pending-state check on the first iteration, lost the already-issued wakeup and
waited the full 10/20 second timeout.

The fix changes one branch so pending state is checked before the first wait.

### Validated result

| Component | Configuration |
| --- | --- |
| Board | Raspberry Pi 5 Model B Rev 1.1 |
| Hypervisor | ESXi-Arm 8.0U3c build 24449057 |
| SSD | Netac NVMe SSD 512 GB |
| PCIe | Gen3 x1 |
| Datastore | GPT + VMFS6 |
| Transport VIB | `nvme-pcie 1.2.4.16-2vmw.803.0.55.24449057` |
| Core VIB | `native-misc-drivers 8.0.3-0.57.24449057` |

Both release VIBs were installed with BootBankInstaller and reboot-tested.
`nvmeBusDriver` attachment fell from 70,456 ms to 429 ms and external
reachability improved from about 66 seconds to 26 seconds. `vmhba0`, VMFS,
OSDATA and both bootbanks returned. Failed NVMe reads and writes remained zero;
no NVMe timeout/reset/DABORT, heartbeat NMI, panic or PSOD was present.

### Verified performance

The Netac 512 GB test used a Debian 13 ARM64 VM on a separate 32 GB thin VMDK
on VMFS6. `fio 3.39` used `libaio`, `direct=1`, one job and a 24 GB test file.

| Workload | Parameters | Result |
| --- | --- | --- |
| Cold sequential read | 256 KiB, QD16, guest caches dropped | **562.242 MB/s** |
| Durable sequential write | 1 MiB, QD16, new extent, `end_fsync=1`, followed by device flush | **160.203 MB/s** |
| SHA-256 verification read | 1 MiB, QD16, verification enabled | **166.037 MB/s**, zero verification errors |

A repeated 8 GB extent produced short cache-sensitive peaks of 848.783 MB/s
read and 871.699 MB/s write. These are not presented as durable media rates.
The 24 GB control above is the validated sustained result. Physical ESXi
counters retained zero failed read/write operations, and focused logs contained
no physical `nvme_pcie` timeout, reset, DABORT, SERROR, panic or PSOD.

### Visual confirmation

The following screenshots are retained from the separately validated v1.0.0
Lexar NM620 256 GB test. They confirm the same transport path (`vmhba0`, local
NVMe and VMFS6), but they do not depict the Netac 512 GB performance run above.

![ESXi NVMe adapter vmhba0 using the nvme_pcie driver](docs/images/esxi-nvme-vmhba0.png)

![Lexar NM620 detected as a local NVMe disk with a VMFS partition](docs/images/esxi-nvme-vmfs6.png)

### Installation

Copy both standalone VIBs to `/tmp`, then dry-run and install each replacement:

```console
esxcli system module parameters set -m vmknvme -p 'vmknvme_compl_world_type=1'
esxcli software vib install -v /tmp/native-misc-drivers-8.0.3-0.57.24449057-community.vib --dry-run --no-sig-check --force
esxcli software vib install -v /tmp/nvme-pcie-rpi5-1.2.4.16-2vmw.803.0.55.24449057-community.vib --dry-run --no-sig-check --force
esxcli software vib install -v /tmp/native-misc-drivers-8.0.3-0.57.24449057-community.vib --no-sig-check --force
esxcli software vib install -v /tmp/nvme-pcie-rpi5-1.2.4.16-2vmw.803.0.55.24449057-community.vib --no-sig-check --force
reboot
```

Each dry run must select only `BootBankInstaller`, replace only the matching
installed VIB and require a reboot. The offline bundle contains both VIBs for
depot/custom-image workflows; the standalone commands above are the
host-verified installation method.

After reboot:

```console
esxcli software vib list | grep -E 'nvme-pcie|native-misc-drivers'
esxcli storage core adapter list | grep nvme
esxcli storage filesystem list
```

### Limitations and rollback

- only ESXi-Arm build 24449057 is supported;
- MSI-X/INTx routing is not fixed; the transport still uses bounded software
  completion processing;
- other NVMe controllers and Raspberry Pi firmware versions are unvalidated.

Do not install without a known-good alternate bootbank and physical console.

## Русский

### Что изменено

Версия 1.1.0 исправляет lost wakeup при загрузке в `vmknvme`. Транспорт
может завершить раннюю raw admin-команду до входа `NVMEExecuteRawCommand` в
ожидание. Штатный код при первой итерации пропускал существующую проверку
pending-state, терял уже отправленное пробуждение и ждал полный таймаут 10/20
секунд.

Изменена одна ветка: состояние проверяется до первого ожидания.

### Проверенный результат

Оба VIB установлены через BootBankInstaller и проверены после перезагрузки на
Raspberry Pi 5 Rev 1.1 с Netac NVMe 512 ГБ, PCIe Gen3 x1 и ESXi-Arm 8.0U3c
build 24449057. Время `nvmeBusDriver attachDevice` снизилось с 70 456 до 429
мс, внешняя доступность — примерно с 66 до 26 секунд. Вернулись `vmhba0`, VMFS,
OSDATA и оба bootbank. Ошибки чтения/записи NVMe остались нулевыми;
timeout/reset/DABORT, heartbeat NMI, panic и PSOD отсутствуют.

### Проверенная производительность

Netac 512 ГБ проверялся в Debian 13 ARM64 VM на отдельном thin VMDK объёмом
32 ГБ в VMFS6. `fio 3.39` использовал `libaio`, `direct=1`, один job и тестовый
файл 24 ГБ.

| Нагрузка | Параметры | Результат |
| --- | --- | --- |
| Последовательное cold-чтение | 256 КиБ, QD16, гостевые кэши очищены | **562,242 МБ/с** |
| Устойчивая последовательная запись | 1 МиБ, QD16, новый extent, `end_fsync=1`, затем flush устройства | **160,203 МБ/с** |
| Чтение с SHA-256 verify | 1 МиБ, QD16, проверка включена | **166,037 МБ/с**, ошибок проверки нет |

Повторная работа с уже выделенным диапазоном 8 ГБ дала короткие
cache-sensitive пики 848,783 МБ/с на чтении и 871,699 МБ/с на записи. Они не
выдаются за устойчивую скорость носителя. Проверенный sustained-результат —
24-гигабайтный контроль выше. Физические счётчики ESXi сохранили нулевые
ошибки операций чтения/записи; в целевых логах отсутствовали физические
`nvme_pcie` timeout, reset, DABORT, SERROR, panic и PSOD.

### Визуальное подтверждение

Скриншоты ниже относятся к отдельно проверенному тесту v1.0.0 с Lexar NM620
256 ГБ. Они подтверждают тот же путь транспорта (`vmhba0`, локальный NVMe и
VMFS6), но не изображают описанный выше тест производительности Netac 512 ГБ.

![NVMe-адаптер vmhba0 в ESXi использует драйвер nvme_pcie](docs/images/esxi-nvme-vmhba0.png)

![Lexar NM620 определяется как локальный NVMe-диск с разделом VMFS](docs/images/esxi-nvme-vmfs6.png)

### Установка

Используйте те же четыре dry-run/install команды из английского раздела выше.
Каждый dry-run должен выбрать только `BootBankInstaller`, заменить только
соответствующий установленный VIB и потребовать перезагрузку. Offline bundle
содержит оба VIB для depot/custom-image; проверенный способ установки — две
standalone-команды.

### Ограничения и откат

- поддерживается только ESXi-Arm build 24449057;
- маршрутизация MSI-X/INTx не исправлена;
- другие NVMe и версии прошивки Raspberry Pi не проверялись.

Не устанавливайте пакет без рабочего alternate bootbank и физической консоли.

## Files / Файлы

- `nvme-pcie-rpi5-1.2.4.16-2vmw.803.0.55.24449057-community.vib` — transport VIB / VIB транспорта;
- `native-misc-drivers-8.0.3-0.57.24449057-community.vib` — VMKNVME wait-fix VIB / VIB исправления VMKNVME;
- `nvme-pcie-rpi5-1.2.4.16-2vmw.803.0.55.24449057-offline-bundle.zip` — offline depot with both VIBs / offline depot с обоими VIB;
- `SHA256SUMS` — checksums / контрольные суммы.
