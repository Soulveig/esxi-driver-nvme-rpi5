# Raspberry Pi 5 NVMe adaptation for ESXi-Arm v1.1.0

**[English](#english) | [Русский](#русский)**

> **Build-specific CommunitySupported package.** Use only with ESXi-Arm
> 8.0U3c build 24449057. Disable Secure Boot and preserve physical console
> access plus a known-good alternate bootbank.

## English

### What changed

The v1.0.0 `nvme_pcie` transport adaptation remains byte-for-byte unchanged.
Version 1.1.0 additionally fixes a startup lost wakeup in `vmknvme`. The
transport can complete an early raw admin command before
`NVMEExecuteRawCommand` starts waiting. Stock code skipped its existing
pending-state check on the first iteration, lost the already-issued wakeup and
waited the full 10/20 second timeout.

The fix changes one branch so pending state is checked before the first wait.
It adds no CQ processing, timeout shortening, busy loop or second completion
owner. The complete stock `native_m.v00` is preserved except for this one-byte
change in its embedded `vmknvme`.

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

Адаптация транспорта `nvme_pcie` из v1.0.0 сохранена byte-for-byte. Версия
1.1.0 дополнительно исправляет lost wakeup при загрузке в `vmknvme`. Транспорт
может завершить раннюю raw admin-команду до входа `NVMEExecuteRawCommand` в
ожидание. Штатный код при первой итерации пропускал существующую проверку
pending-state, терял уже отправленное пробуждение и ждал полный таймаут 10/20
секунд.

Изменена одна ветка: состояние проверяется до первого ожидания. Новый
обработчик CQ, сокращение таймаутов, busy loop или второй владелец completion не
добавляются. Полный штатный `native_m.v00` сохранён, кроме этого однобайтового
изменения во встроенном `vmknvme`.

### Проверенный результат

Оба VIB установлены через BootBankInstaller и проверены после перезагрузки на
Raspberry Pi 5 Rev 1.1 с Netac NVMe 512 ГБ, PCIe Gen3 x1 и ESXi-Arm 8.0U3c
build 24449057. Время `nvmeBusDriver attachDevice` снизилось с 70 456 до 429
мс, внешняя доступность — примерно с 66 до 26 секунд. Вернулись `vmhba0`, VMFS,
OSDATA и оба bootbank. Ошибки чтения/записи NVMe остались нулевыми;
timeout/reset/DABORT, heartbeat NMI, panic и PSOD отсутствуют.

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
