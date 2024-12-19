import time
from journal_monitor.logfile_journal_monitor import LogfileJournalMonitor
from ptp4l_monitor.ptp4l_parser import Ptp4lParser


def main():
    monitor = (
        LogfileJournalMonitor("sub_ptp_log/sub_ptp4l@***REMOVED***.log")
        .only_current_boot()
        .only_systemd_unit("ptp4l")
    )

    parser = Ptp4lParser()

    while True:
        new_entries = monitor.poll()
        for e in new_entries:
            parser.step_state_machine(e)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
