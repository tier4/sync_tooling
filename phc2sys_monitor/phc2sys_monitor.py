import time
from journal_monitor.logfile_journal_monitor import LogfileJournalMonitor
from phc2sys_parser import Phc2SysParser


def main():
    monitor = (
        LogfileJournalMonitor("sub_ptp_log/sub_phc2sys_enp5s0f0_to_enp3s0.log")
        .only_current_boot()
        .only_systemd_unit("phc2sys")
    )

    parser = Phc2SysParser()

    while True:
        new_entries = monitor.poll()
        for e in new_entries:
            parser.step_state_machine(e)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
