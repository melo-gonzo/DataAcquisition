from threading import Thread
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import serial
import time


class Daq:
    def __init__(self, samples=None, max_page_points=100000):
        self.working_dir = '/home/carmelo/Documents/DataAcquisition/'
        self.samples = samples
        self.max_page_points = max_page_points
        # self.channels is always the number of lines printed in Arduino program, besides the
        # counter and duration of collection. example, if you have two analog sensors in A0
        # through A5, self.channels = 6
        self.channels = 6
        # self.plot_channels is always a list of lists. The number of sub-lists will be the
        # number of subplots that you have. You can mix and match indicies, depending on what
        # sensors you have going into each channel. Example: If you have accelerometers on
        # channels 0, 1 and 2 - put those on one subplot. If you have pressure transducers on 3,
        # 4, and 5 - put those on another subplot.
        self.plot_channels = [[0, 1, 2], [3, 4, 5]]
        # self.ranges is always a list of lists. It is the expected y-axis range for each subplot.
        # This must always be the same size as self.plot_channels.
        self.ranges = [[0, 1050], [0, 1050]]
        self.log_data = True
        self.data_file = []
        try:
            self.total_plots = len(self.plot_channels)
        except TypeError:
            self.total_plots = 1
        if self.samples is None:
            self.data_log = np.zeros((500, 2 + self.channels))
        else:
            self.data_log = np.zeros((self.samples, 2 + self.channels))

    def open_data_file(self):
        self.data_file = open(
            self.working_dir + 'test_logs' + str(np.round(time.time(), 2)) + '.txt', 'a+',
            newline='')

    def set_log_data(self, val):
        self.log_data = val


class Keepers:
    def __init__(self):
        self.k = 0
        self.c = 0
        self.started = 0
        self.page_points = 0
        self.str_data = ''
        self.test = True
        self.started = False

    def reset_keepers(self):
        self.k = 0
        self.c = 0
        self.started = 0
        self.page_points = 0
        self.str_data = ''
        self.test = True
        self.started = False

    def set_plot_object(self, ln_ax):
        self.line = ln_ax[0]
        self.ax = ln_ax[1]


### Workers
def initalize_arduino(com, baud=115200):
    a = serial.Serial(com, baud, timeout=2)
    time.sleep(1)
    do_reset(a)
    a.flushOutput()
    a.flushInput()
    a.write(b's')
    print('D2 HIGH')
    return a


def start_daq(a, daq, keepers):
    daq.set_log_data(True)
    daq.open_data_file()
    if daq.samples is None:
        daq.samples = keepers.k
        daq.set_log_data(False)
    time.sleep(0.001)
    if daq.log_data:
        while keepers.k < daq.samples:
            try:
                keepers, daq = read_collect_data(a, keepers, daq)
                keepers, daq = write_data(keepers, daq)
            except KeyboardInterrupt:
                do_reset(a)
                print('Finished Recording')
                break
        keepers, daq = write_data(keepers, daq)
        daq.data_file.close()
    else:
        while True:
            try:
                keepers, daq = read_collect_data(a, keepers, daq)
            except KeyboardInterrupt:
                do_reset(a)
                print('Finished Recording')
                break
    print('Finished Recording')
    do_reset(a)
    final_plot(keepers, daq)
    return daq


def read_collect_data(a, keepers, daq):
    try:
        data = a.read(a.inWaiting()).decode('UTF-8')
        if data and keepers.test:
            if data[0].split(',')[0] == '1':
                keepers.started = True
                keepers.test = False
        if data and keepers.started:
            while data[-1] != '\n':
                data += a.read(a.inWaiting()).decode('UTF-8')
            keepers.str_data += data
            data = data.strip().split('\r\n')
            old_k = keepers.k
            keepers.page_points = keepers.page_points + len(data)
            keepers.k = keepers.k + len(data)
            keepers.c += 1
            pulse(keepers.c, keepers.k)
            try:
                if daq.log_data:
                    daq.data_log[old_k:keepers.k, :] = np.array([n.split(',')[:] for n in data])
                else:
                    ndata = np.array([n.split(',')[:] for n in data])
                    odata = daq.data_log[ndata.shape[0]:daq.data_log.shape[0], :]
                    daq.data_log[:odata.shape[0], :] = odata
                    daq.data_log[odata.shape[0]:, :] = ndata
                    keepers.k = 0
            except Exception:
                try:
                    daq.data_log[old_k:, :] = np.array([n.split(',')[:] for n in data])[
                                              0:daq.samples - old_k]
                except Exception:
                    print('Data Write Error')
                    keepers.reset_keepers()
                    do_reset(a)
            # draw_line(keepers, daq)
    except UnicodeDecodeError:
        print('Decode Error')
    return keepers, daq


def write_data(keepers, daq):
    if keepers.page_points >= daq.max_page_points or keepers.k >= daq.samples or keepers.page_points > 100:
        _ = daq.data_file.write(keepers.str_data)
        if keepers.k < daq.samples and keepers.page_points >= daq.max_page_points:
            daq.data_file.close()
            daq.open_data_file()
            keepers.page_points = 0
            print('New File')
        keepers.str_data = ''
    return keepers, daq


### Utilities
def pulse(c, k):
    if c % 20 == 0:
        print(str(k) + ' Samples Collected')


def do_reset(a):
    a.setDTR(True)
    time.sleep(0.1)
    a.setDTR(False)
    time.sleep(0.1)
    print('Reset Arduino')


def final_plot(keepers, daq):
    total_plots = daq.total_plots
    if daq.log_data:
        for k in range(total_plots):
            try:
                t_end = np.nonzero(daq.data_log[:, 0] == 0)[0][0] - 1
            except IndexError:
                t_end = len(daq.data_log[:, 0]) - 1
            keepers.ax[k].set_xlim([0, daq.data_log[t_end, 1]])
    else:
        for ii in range(total_plots):
            keepers.ax[ii].set_xlim([daq.data_log[0, 1], daq.data_log[-1, 1]])
    plt.show(block=True)


def make_plot(daq):
    total_plots = daq.total_plots
    if total_plots > 3:
        fig, ax = plt.subplots(total_plots // 2 + 1, 2)
        fig.subplots_adjust(wspace=0.4, hspace=0.5)
    else:
        fig, ax = plt.subplots(total_plots, 1)
    ax = ax.reshape(-1, )[:total_plots + 1]
    ax = [ax] if total_plots == 1 else ax
    line = []
    for k in range(total_plots):
        try:
            zrs = np.zeros((1, len(daq.plot_channels[k])))
            labs = ['A' + str(st) for st in list(daq.plot_channels[k])]
        except TypeError:
            zrs = np.zeros((1, 1))
            labs = ['A' + str(daq.plot_channels[0])]
        ax[k].set_ylim([daq.ranges[k][0], daq.ranges[k][1]])
        line.append(ax[k].plot(zrs, zrs, linewidth=2))
        ax[k].legend(line[k], labs, loc=1)
        ax[k].set_xlabel('Time (ms)')
        ax[k].set_ylabel('Amplitude')
    plt.show(block=False)
    plt.pause(0.001)
    return line, ax


def draw_line(keepers, daq):
    pc = daq.plot_channels
    total_plots = daq.total_plots
    data = daq.data_log
    k = keepers.k
    if daq.log_data:
        for p in range(total_plots):
            try:
                if data[k - 1, 1] < 5000:
                    # keepers.ax[p].set_xlim([data[0, 1], data[k - 1, 1]])
                    keepers.ax[p].set_xlim([0, data[k - 1, 1]])
                else:
                    keepers.ax[p].set_xlim(
                        [data[data[:, 1] > (data[k - 1, 1] - 5000), 1][0], data[k - 1, 1]])
            except IndexError:
                keepers.ax[p].set_xlim([0, data[-1, 1]])
            for idx, n in enumerate(pc[p]):
                keepers.line[p][idx].set_data(data[:k, 1], data[:k, n + 2])
        plt.pause(0.0001)
    else:
        for p in range(total_plots):
            keepers.ax[p].set_xlim(data[0, 1], data[-1, 1])
            for idx, n in enumerate(pc[p]):
                keepers.line[p][idx].set_data(data[:, 1], data[:, n + 2])
        plt.pause(0.0001)


### Main
if __name__ == '__main__':
    # Inputs to Daq() are: Number of samples to collect, and number of points to save per text
    # file. If you want to stream continuously and not save any information, dont give any
    # arguments. To save 1000 points, with 100 points per page: Daq(1000, 100). To collect 1000
    # points on the same text file, Daq(1000)
    daq = Daq(1000)
    keepers = Keepers()
    keepers.set_plot_object(make_plot(daq))
    # Select the correct com port.
    a = initalize_arduino('/dev/ttyACM0')
    daq_thread = Thread(target=start_daq, args=(a, daq, keepers,))
    plot_thread = Thread(target=draw_line, args=(keepers, daq,))
    daq_thread.start()
    plot_thread.start()


