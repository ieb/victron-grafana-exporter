import os
import time 
import socket

import logging
import traceback
log = logging.getLogger(__name__)


class OsMeter:
    def __init__(self):
        self.stats = {}
        pass

    def read_proc(self,name):
        with open(name, "r")  as f:
            return f.readlines()
    def readOs(self,cmd):
        with os.popen(cmd) as f:
            return f.readlines()

    def collect_cpu(self, source, hostname, nowSeconds, stat):
        payload = []
        for l in stat:
            if l.startswith('cpu'):
                s = l.strip().split()
                k = f'stats_{s[0]}'
                if k in self.stats:
                    p = self.stats[k]
                else:
                    p = s
                diff = [0] * 12
                diff.append(s[0])
                t = 0
                for x in range(2,len(s)):
                    diff[x] = int(s[x])-int(p[x])
                    t += diff[x] 
                for x in range(1,len(s)):
                    if t == 0:
                        diff[x] = 0
                    else:
                        diff[x] = float(diff[x])/float(t) 
                self.stats[k] = s
                metric_name = s[0]
                if metric_name == 'cpu':
                    metric_name = 'cpu-total'
                cpuinfo = []
                cpuinfo.append(f'usage_user={diff[2]}')
                cpuinfo.append(f'usage_nice={diff[3]}')
                cpuinfo.append(f'usage_system={diff[4]}')
                cpuinfo.append(f'usage_idle={diff[5]}')
                cpuinfo.append(f'usage_iowait={diff[6]}')
                cpuinfo.append(f'usage_irq={diff[7]}')
                cpuinfo.append(f'usage_softirq={diff[8]}')
                cpuinfo.append(f'usage_steal={diff[9]}')
                cpuinfo.append(f'usage_guest={diff[10]}')
                cpuinfo.append(f'usage_guest_nice={diff[11]}')
                cpuline = f'cpu,cpu={metric_name},source={source},host={hostname} {",".join(cpuinfo)} {nowSeconds}000000000'
                payload.append(cpuline)
        return payload

    def collect_kernel(self, source, hostname, nowSeconds, stat):
        kernel = []
        for l in stat:
            s = l.strip().split()
            if s[0] == 'intr':
                # interrupts
                kernel.append(f'interrupts={s[1]}i')
            elif s[0] == 'ctxt':
                kernel.append(f'context_switches={s[1]}i')
            elif s[0] == 'btime':
                kernel.append(f'boot_time={s[1]}i')
            elif s[0] == 'processes':
                kernel.append(f'processes_forked={s[1]}i')
            elif s[0] == 'procs_running':
                kernel.append(f'procs_running={s[1]}i')
            elif s[0] == 'procs_blocked':
                kernel.append(f'procs_blocked={s[1]}i')
        entropy = self.read_proc('/proc/sys/kernel/random/entropy_avail')
        kernel.append(f'entropy_avail={entropy[0].strip()}i')
        return [f'kernel,source={source},host=nanopi {",".join(kernel)} {nowSeconds}000000000']

    def collect_system(self, source, hostname, nowSeconds, stat):
        system = []
        n_cpus = 0
        for l in stat:
            if l.startswith('cpu'):
                n_cpus = n_cpus + 1
            if l.startswith('btime '):
                uptime = nowSeconds-int(l.strip().split()[1])
                system.append(f'uptime={uptime}u')
                utime_days = uptime // (3600*24)
                utime_hours = (uptime % (3600*24)) // 3600 
                utime_minutes = (uptime % (3600)) // 60
                system.append(f'uptime_format="{utime_days} days, {utime_hours}:{utime_minutes:02d}"')                
        n_cpus = n_cpus - 1
        loadavg =  self.read_proc('/proc/loadavg')[0].split()
        whoshere = self.readOs('who')
        system.append(f'load1={float(loadavg[0])}')
        system.append(f'load5={float(loadavg[1])}')
        system.append(f'load15={float(loadavg[2])}')
        system.append(f'n_cpus={n_cpus}i')



        unique_users = {}
        for x in whoshere:
            u = x.split()
            unique_users[u[0]] = 1
        system.append(f'n_unique_users={len(unique_users)}i')
        system.append(f'n_users={len(whoshere)}i')

        return [ f'system,source={source},host={hostname} {",".join(system)} {nowSeconds}000000000' ]



    def collect_process_stats(self, source, hostname, nowSeconds):
        """
        Feeling lazy on this on, Gemini 2.5 pro generated. TBH, still not convinced

        Reads the Linux /proc filesystem to gather process statistics and formats them
        into an InfluxDB Line Protocol string.

        The 'total' field represents the sum of processes successfully categorized by state.
        'total_threads' is the sum of threads from all processes where thread count
        could be read.

        Args:
            hostname_override (str, optional): If provided, this hostname will be used
                in the output string. Otherwise, the system's hostname is used.

        Returns:
            str: A string formatted in InfluxDB Line Protocol.
        """
        stats_counts = {
            "blocked": 0,  # D state - uninterruptible disk sleep
            "dead": 0,     # X state - dead (should not be seen)
            "idle": 0,     # I state - Idle kernel threads / tasks on idle CPU
            "paging": 0,   # W state - paging (pre-2.6 kernels, rare)
            "running": 0,  # R state - running or runnable
            "sleeping": 0, # S state - interruptible sleep
            "stopped": 0,  # T, t states - stopped by job control or debugger
            "zombies": 0,  # Z state - zombie
            "unknown": 0,  # Any other state encountered
        }
        total_threads_sum = 0
        
        pid_dirs = [pid_str for pid_str in os.listdir('/proc') if pid_str.isdigit()]
        for pid in pid_dirs:
            try:
                stat_path = f'/proc/{pid}/stat'
                status_path = f'/proc/{pid}/status'
                
                process_state = None
                # Read process state from /proc/[pid]/stat (3rd field)
                with open(stat_path, 'r') as f_stat:
                    stat_line = f_stat.readline().split()
                    if len(stat_line) > 2: # Ensure stat line is well-formed
                        process_state = stat_line[2]
                    else:
                        continue # Skip malformed stat line

                # Read thread count from /proc/[pid]/status
                threads_for_pid = 0 # Default if "Threads:" not found or status unreadable
                try:
                    with open(status_path, 'r') as f_status:
                        for line in f_status:
                            if line.startswith("Threads:"):
                                threads_for_pid = int(line.split()[1])
                                break
                except IOError: 
                    # Cannot read status file (e.g., permissions), threads_for_pid remains 0
                    pass
                except ValueError:
                    # "Threads:" line malformed
                    pass
                
                total_threads_sum += threads_for_pid
                
                # Categorize process based on state
                if process_state == 'R':
                    stats_counts["running"] += 1
                elif process_state == 'S':
                    stats_counts["sleeping"] += 1
                elif process_state == 'D':
                    stats_counts["blocked"] += 1
                elif process_state == 'Z':
                    stats_counts["zombies"] += 1
                elif process_state in ['T', 't']:
                    stats_counts["stopped"] += 1
                elif process_state == 'W':
                    stats_counts["paging"] += 1
                elif process_state == 'X':
                    stats_counts["dead"] += 1
                elif process_state == 'I': # Typically kernel idle threads
                    stats_counts["idle"] += 1
                else:
                    stats_counts["unknown"] += 1
            
            except FileNotFoundError:
                # Process terminated between os.listdir() and file access. Skip.
                pass
            except IOError: 
                # PermissionError (subclass of IOError) or other I/O issue reading stat. Skip.
                pass
            except Exception: 
                # Catch any other unexpected errors for a specific PID & skip it.
                # You might want to log this for debugging.
                # print(f"Unexpected error processing PID {pid}: {e}", file=sys.stderr)
                pass

        # 'total' is the sum of all successfully categorized process states
        total_processes_from_states = sum(stats_counts.values())


        
        # Prepare fields for the InfluxDB line, matching the requested order
        fields_data = {
            "blocked": stats_counts["blocked"],
            "dead": stats_counts["dead"],
            "idle": stats_counts["idle"],
            "paging": stats_counts["paging"],
            "running": stats_counts["running"],
            "sleeping": stats_counts["sleeping"],
            "stopped": stats_counts["stopped"],
            "total": total_processes_from_states, 
            "total_threads": total_threads_sum,
            "unknown": stats_counts["unknown"],
            "zombies": stats_counts["zombies"],
        }
        
        # Ensure the specific order as in the example
        ordered_field_keys = [
            "blocked", "dead", "idle", "paging", "running", "sleeping", 
            "stopped", "total", "total_threads", "unknown", "zombies"
        ]
        fields_string_parts = [f"{key}={fields_data[key]}i" for key in ordered_field_keys]
        fields_string = ",".join(fields_string_parts)

        # Assemble the final InfluxDB line protocol string
        line = f"processes,source={source},host={hostname} {fields_string} {nowSeconds}000000000"
        
        return [line]

    def read_proc_list(self, file):
        lines = self.read_proc(file)
        pl = {}
        for line in lines:
            if ':' in line:
                k, v = line.strip().split(':', 1)
                pl[k.strip()] = v.strip().split()[0]
        return pl

    def collect_mem(self, source, hostname, nowSeconds):
        mem = []
        mem_info = self.read_proc_list("/proc/meminfo")

        total = int(mem_info.get("MemTotal", 0))
        free = int(mem_info.get("MemFree", 0))
        buffers = int(mem_info.get("Buffers", 0))
        cached = int(mem_info.get("Cached", 0))
        sreclaimable = int(mem_info.get("SReclaimable", 0))
        available = int(mem_info.get("MemAvailable", 0))

        used = total - free - buffers - cached - sreclaimable if total > 0 else 0
        available_percent = (100 * available / total) if total > 0 else 0
        used_percent = (100* used / total) if total > 0 else 0

        mem.append(f'total={total}u')
        mem.append(f'free={free}u')
        mem.append(f'available={available}u')
        mem.append(f'cached={cached}u')
        mem.append(f'sreclaimable={sreclaimable}u')
        mem.append(f'used={used}u')
        mem.append(f'used_percent={used_percent}')
        mem.append(f'available_percent={available_percent}')
        mem.append(f'active={mem_info.get("Active", "0")}u')
        mem.append(f'buffered={mem_info.get("Buffers", "0")}u')
        mem.append(f'commit_limit={mem_info.get("CommitLimit", "0")}u')
        mem.append(f'committed_as={mem_info.get("Committed_AS", "0")}u')
        mem.append(f'dirty={mem_info.get("Dirty", "0")}u')
        mem.append(f'high_free={mem_info.get("HighFree", "0")}u')
        mem.append(f'high_total={mem_info.get("HighTotal", "0")}u')
        mem.append(f'huge_page_size={mem_info.get("Hugepagesize", "0")}u')
        mem.append(f'huge_pages_free={mem_info.get("HugePages_Free", "0")}u')
        mem.append(f'huge_pages_total={mem_info.get("HugePages_Total", "0")}u')
        mem.append(f'inactive={mem_info.get("Inactive", "0")}u')
        mem.append(f'low_free={mem_info.get("LowFree", "0")}u')
        mem.append(f'low_total={mem_info.get("LowTotal", "0")}u')
        mem.append(f'mapped={mem_info.get("Mapped", "0")}u')
        mem.append(f'page_tables={mem_info.get("PageTables", "0")}u')
        mem.append(f'shared={mem_info.get("Shmem", "0")}u')
        mem.append(f'slab={mem_info.get("Slab", "0")}u')
        mem.append(f'sunreclaim={mem_info.get("SReclaimable", "0")}u')
        mem.append(f'swap_cached={mem_info.get("SwapCached", "0")}u')
        mem.append(f'swap_free={mem_info.get("SwapFree", "0")}u')
        mem.append(f'swap_total={mem_info.get("SwapTotal", "0")}u')
        mem.append(f'vmalloc_chunk={mem_info.get("VmallocChunk", "0")}u')
        mem.append(f'vmalloc_total={mem_info.get("VmallocTotal", "0")}u')
        mem.append(f'vmalloc_used={mem_info.get("VmallocUsed", "0")}u')
        mem.append(f'write_back={mem_info.get("Writeback", "0")}u')
        mem.append(f'write_back_tmp={mem_info.get("WritebackTmp", "0")}u')



        # mem,host=nanopi active=39882752u,available=111366144u,available_percent=21.31517674451422,buffered=323584u,cached=114286592u,commit_limit=261234688u,committed_as=531718144u,dirty=0u,free=10350592u,high_free=0u,high_total=0u,huge_page_size=0u,huge_pages_free=0u,huge_pages_total=0u,inactive=427667456u,low_free=10350592u,low_total=522473472u,mapped=91815936u,page_tables=7512064u,shared=1744896u,slab=20877312u,sreclaimable=6533120u,sunreclaim=14344192u,swap_cached=0u,swap_free=0u,swap_total=0u,total=522473472u,used=397512704u,used_percent=76.08284923602781,vmalloc_chunk=0u,vmalloc_total=520093696u,vmalloc_used=4640768u,write_back=0u,write_back_tmp=0u 1747289355000000000

        #> swap,host=nanopi free=0u,total=0u,used=0u,used_percent=0 1747289355000000000
        #> swap,host=nanopi in=0u,out=0u 1747289355000000000

        swap_used = int(mem_info.get("SwapCached",0))
        swap_total = int(mem_info.get("SwapTotal",0))
        swap_percent = 100*float(swap_used)/float(swap_total) if swap_total > 0 else 0
        swap = []
        swap.append(f'free={int(mem_info.get("SwapFree",0))*10240}u')
        swap.append(f'total={swap_total*10240}u')
        swap.append(f'used={swap_used*10240}u')
        swap.append(f'used_percent={swap_percent}u')
        swap.append(f'in=0u')
        swap.append(f'out=0u')

        return [ f'mem,source={source},host={hostname} {",".join(mem)} {nowSeconds}000000000', f'swap,source={source},host={hostname} {",".join(swap)} {nowSeconds}000000000' ]

    def collect_diskio(self, source, hostname, nowSeconds):
        disks = []
        disk_info = self.read_proc("/proc/diskstats")
        for line in disk_info:
            diskstats = line.strip().split()
            diskinfo = []

            diskinfo.append(f'io_time={diskstats[12]}u')
            diskinfo.append(f'ops_in_progress={diskstats[11]}u')
            diskinfo.append(f'merged_reads={diskstats[4]}u')
            diskinfo.append(f'merged_writes={diskstats[8]}u')
            diskinfo.append(f'read_bytes={int(diskstats[5])*512}u')
            diskinfo.append(f'read_time={diskstats[6]}u')
            diskinfo.append(f'reads={diskstats[3]}u')
            diskinfo.append(f'weighted_io_time={diskstats[13]}u')
            diskinfo.append(f'write_bytes={int(diskstats[9])*512}u')
            diskinfo.append(f'write_time={diskstats[10]}u')
            diskinfo.append(f'writes={diskstats[7]}u')
            # > diskio,host=nanopi,name=mmcblk1p5 io_time=1248150u,iops_in_progress=2u,merged_reads=161u,merged_writes=84147u,read_bytes=762774528u,read_time=21754u,reads=18604u,weighted_io_time=120989u,write_bytes=1170444288u,write_time=99234u,writes=200354u 1747289355000000000
            disks.append(f'diskio,source={source},host={hostname},name={diskstats[2]} {",".join(diskinfo)} {nowSeconds}000000000')
        return disks

    def convert_to_dict(self,lines, pos):
        d = {}
        for line in lines:
            l = line.strip().split()
            d[l[pos]] = l
        return d


    def collect_disk(self, source, hostname, nowSeconds):
        disks = []
        fsai = self.convert_to_dict(self.readOs('df -ai'),5)
        fsa = self.convert_to_dict(self.readOs('df -a'),5)
        mount = self.convert_to_dict(self.readOs('mount'),2)
        for k, v in fsa.items():
            if v[0].startswith('/dev/'):
                device = v[0][5:]                    
                fs_inodes = fsai[k]
                fs = fsa[k]
                fs_mount = mount[k]

                diskinfo = []
                inodes_total = float(fs_inodes[1])
                inode_used_percent = 100*float(fs_inodes[2])/inodes_total  if inodes_total > 0 else 0
                total = float(fs[1])
                used_percent = 100*float(fs[2])/total if total > 0 else 0
                diskinfo.append(f'free={1024*int(fs[3])}u')
                diskinfo.append(f'inodes_free={fs_inodes[3]}u')
                diskinfo.append(f'inodes_total={int(inodes_total)}u')
                diskinfo.append(f'inodes_used={fs_inodes[2]}u')
                diskinfo.append(f'inodes_used_percent={inode_used_percent}')
                diskinfo.append(f'total={int(total)}u')
                diskinfo.append(f'used={1024*int(fs[2])}u')
                diskinfo.append(f'used_percent={used_percent}')
                mode = fs_mount[5].strip()[1:-1].split(',')[0]
                # disk,device=mmcblk1p3,fstype=ext4,host=nanopi,mode=rw,path=/ free=1549216768u,inodes_free=497914u,inodes_total=516096u,inodes_used=18182u,inodes_used_percent=3.5229879712301586,total=2006240256u,used=362212352u,used_percent=18.949818657152196 1747289355000000000
                disks.append(f'disk,source={source},host={hostname},device={device},fstype={fs_mount[4]},mode={mode},path={fs_mount[2]} {",".join(diskinfo)} {nowSeconds}000000000')
        return disks

    def collect_net(self, source, hostname, nowSeconds):
        '''

        root@nanopi:/data/grafana-exporter# cat /proc/net/dev
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo:  317397    2807    0    0    0     0          0         0   317397    2807    0    0    0     0       0          0
  can0: 2197816  274727    0    0    0     0          0         0   244688   30586    0    0    0     0       0          0
  eth0:       0       0    0    0    0     0          0         0        0       0    0    0    0     0       0          0
 wifi0: 8194292   36571    0  881    0     0          0         0 11438736   30456    0    0    0     0       0          0
   ap0:       0       0    0    0    0     0          0         0        0       0    0  271    0     0       0          0
ll-eth0:       0       0    0    0    0     0          0         0      218       3    0    0    0     0       0          0
root@nanopi:/data/grafana-exporter# 
        > net,host=nanopi,interface=can0 bytes_recv=131062976u,bytes_sent=14598992u,drop_in=0u,drop_out=0u,err_in=0u,err_out=0u,packets_recv=16382872u,packets_sent=1824874u,speed=-1i 1747289355000000000
        > net,host=nanopi,interface=eth0 bytes_recv=0u,bytes_sent=0u,drop_in=0u,drop_out=0u,err_in=0u,err_out=0u,packets_recv=0u,packets_sent=0u,speed=-1i 1747289355000000000

        > net,host=nanopi,interface=all icmp_inaddrmaskreps=0i,icmp_inaddrmasks=0i,icmp_incsumerrors=0i,icmp_indestunreachs=64i,icmp_inechoreps=0i,icmp_inechos=0i,icmp_inerrors=0i,icmp_inmsgs=64i,icmp_inparmprobs=0i,icmp_inredirects=0i,icmp_insrcquenchs=0i,icmp_intimeexcds=0i,icmp_intimestampreps=0i,icmp_intimestamps=0i,icmp_outaddrmaskreps=0i,icmp_outaddrmasks=0i,icmp_outdestunreachs=26i,icmp_outechoreps=0i,icmp_outechos=0i,icmp_outerrors=0i,icmp_outmsgs=26i,icmp_outparmprobs=0i,icmp_outredirects=0i,icmp_outsrcquenchs=0i,icmp_outtimeexcds=0i,icmp_outtimestampreps=0i,icmp_outtimestamps=0i,icmpmsg_intype3=64i,icmpmsg_outtype3=26i,ip_defaultttl=64i,ip_forwarding=2i,ip_forwdatagrams=0i,ip_fragcreates=0i,ip_fragfails=0i,ip_fragoks=0i,ip_inaddrerrors=1i,ip_indelivers=2037558i,ip_indiscards=0i,ip_inhdrerrors=0i,ip_inreceives=2100418i,ip_inunknownprotos=0i,ip_outdiscards=0i,ip_outnoroutes=0i,ip_outrequests=1804414i,ip_reasmfails=3i,ip_reasmoks=13i,ip_reasmreqds=29i,ip_reasmtimeout=3i,tcp_activeopens=14190i,tcp_attemptfails=0i,tcp_currestab=10i,tcp_estabresets=85i,tcp_incsumerrors=0i,tcp_inerrs=2i,tcp_insegs=1411971i,tcp_maxconn=-1i,tcp_outrsts=22i,tcp_outsegs=1570016i,tcp_passiveopens=266i,tcp_retranssegs=5216i,tcp_rtoalgorithm=1i,tcp_rtomax=120000i,tcp_rtomin=200i,udp_ignoredmulti=5759i,udp_incsumerrors=0i,udp_indatagrams=1529281i,udp_inerrors=0i,udp_noports=26i,udp_outdatagrams=306912i,udp_rcvbuferrors=0i,udp_sndbuferrors=0i,udplite_ignoredmulti=0i,udplite_incsumerrors=0i,udplite_indatagrams=0i,udplite_inerrors=0i,udplite_noports=0i,udplite_outdatagrams=0i,udplite_rcvbuferrors=0i,udplite_sndbuferrors=0i 1747289355000000000
        '''
        network = []
        net = self.read_proc('/proc/net/dev')
        for line in net:
            n = line.strip().split()
            n[0] = n[0][:-1]
            if n[0].startswith('can') or n[0].startswith('eth') or n[0].startswith('wifi'):
                interface = []
                interface.append(f'bytes_recv={n[1]}u')
                interface.append(f'bytes_sent={n[9]}u')
                interface.append(f'drop_in={n[4]}u')
                interface.append(f'drop_out={n[12]}u')
                interface.append(f'err_in={n[3]}u')
                interface.append(f'err_out={n[11]}u')
                interface.append(f'packets_recv={n[2]}u')
                interface.append(f'packets_sent={n[10]}u')
                interface.append(f'speed=-1i')
                # > net,host=nanopi,interface=can0 bytes_recv=131062976u,bytes_sent=14598992u,drop_in=0u,drop_out=0u,err_in=0u,err_out=0u,packets_recv=16382872u,packets_sent=1824874u,speed=-1i 1747289355000000000
                network.append(f'net,source={source},host={hostname},interface={n[0]} {",".join(interface)} {nowSeconds}000000000')
        '''
        root@nanopi:/data/grafana-exporter# cat /proc/net/snmp
        Ip: Forwarding DefaultTTL InReceives InHdrErrors InAddrErrors ForwDatagrams InUnknownProtos InDiscards InDelivers OutRequests OutDiscards OutNoRoutes ReasmTimeout ReasmReqds ReasmOKs ReasmFails FragOKs FragFails FragCreates
        Ip: 2 64 108088 0 1 0 0 0 102356 82395 0 0 0 2 1 0 0 0 0
        Icmp: InMsgs InErrors InCsumErrors InDestUnreachs InTimeExcds InParmProbs InSrcQuenchs InRedirects InEchos InEchoReps InTimestamps InTimestampReps InAddrMasks InAddrMaskReps OutMsgs OutErrors OutDestUnreachs OutTimeExcds OutParmProbs OutSrcQuenchs OutRedirects OutEchos OutEchoReps OutTimestamps OutTimestampReps OutAddrMasks OutAddrMaskReps
        Icmp: 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3 0 3 0 0 0 0 0 0 0 0 0 0
        IcmpMsg: OutType3
        IcmpMsg: 3
        Tcp: RtoAlgorithm RtoMin RtoMax MaxConn ActiveOpens PassiveOpens AttemptFails EstabResets CurrEstab InSegs OutSegs RetransSegs InErrs OutRsts InCsumErrors
        Tcp: 1 200 120000 -1 976 37 0 0 10 62168 71078 291 0 4 0
        Udp: InDatagrams NoPorts InErrors OutDatagrams RcvbufErrors SndbufErrors InCsumErrors IgnoredMulti
        Udp: 99943 3 0 16725 0 0 0 228
        UdpLite: InDatagrams NoPorts InErrors OutDatagrams RcvbufErrors SndbufErrors InCsumErrors IgnoredMulti
        UdpLite: 0 0 0 0 0 0 0 0
        root@nanopi:/data/grafana-exporter# ')
        '''
        snmp = self.read_proc('/proc/net/snmp')
        snmp_map = {}
        for line in snmp:
            n = line.strip().split()
            if n[0] in snmp_map:
                for i in range(1, len(n)):
                    name = snmp_map[n[0]]['headers'][i]
                    snmp_map[n[0]]['data'][name] = n[i]
            else:
                snmp_map[n[0]] = {
                    'headers': n,
                    'data': {}
                }
        netstats = []
        icmp_stats = snmp_map['Icmp:']['data'] if 'Icmp:' in  snmp_map else {} 
        netstats.append(f'icmp_inaddrmaskreps={icmp_stats.get("InAddrMaskReps","0")}i')
        netstats.append(f'icmp_inaddrmasks={icmp_stats.get("InAddrMasks","0")}i')
        netstats.append(f'icmp_incsumerrors={icmp_stats.get("InCsumErrors","0")}i')
        netstats.append(f'icmp_indestunreachs={icmp_stats.get("InDestUnreachs","0")}i') 
        netstats.append(f'icmp_inechoreps={icmp_stats.get("InEchoReps","0")}i')
        netstats.append(f'icmp_inechos={icmp_stats.get("InEchos","0")}i')
        netstats.append(f'icmp_inerrors={icmp_stats.get("InErrors","0")}i')
        netstats.append(f'icmp_inmsgs={icmp_stats.get("InMsgs","0")}i')
        netstats.append(f'icmp_inparmprobs={icmp_stats.get("InParmProbs","0")}i') 
        netstats.append(f'icmp_inredirects={icmp_stats.get("InRedirects","0")}i') 
        netstats.append(f'icmp_insrcquenchs={icmp_stats.get("InSrcQuenchs","0")}i') 
        netstats.append(f'icmp_intimeexcds={icmp_stats.get("InTimeExcds","0")}i') 
        netstats.append(f'icmp_intimestampreps={icmp_stats.get("InTimestampReps","0")}i') 
        netstats.append(f'icmp_intimestamps={icmp_stats.get("InTimestamps","0")}i') 

                    
        netstats.append(f'icmp_outaddrmaskreps={icmp_stats.get("OutAddrMaskReps","0")}i') 
        netstats.append(f'icmp_outaddrmasks={icmp_stats.get("OutAddrMasks","0")}i')
        netstats.append(f'icmp_outdestunreachs={icmp_stats.get("OutDestUnreachs","0")}i') 
        netstats.append(f'icmp_outechoreps={icmp_stats.get("OutEchoReps","0")}i')
        netstats.append(f'icmp_outechos={icmp_stats.get("OutEchos","0")}i') 
        netstats.append(f'icmp_outerrors={icmp_stats.get("OutErrors","0")}i') 
        netstats.append(f'icmp_outmsgs={icmp_stats.get("OutMsgs","0")}i') 
        netstats.append(f'icmp_outparmprobs={icmp_stats.get("OutParmProbs","0")}i') 
        netstats.append(f'icmp_outredirects={icmp_stats.get("OutRedirects","0")}i') 
        netstats.append(f'icmp_outsrcquenchs={icmp_stats.get("OutSrcQuenchs","0")}i') 
        netstats.append(f'icmp_outtimeexcds={icmp_stats.get("OutTimeExcds","0")}i') 
        netstats.append(f'icmp_outtimestampreps={icmp_stats.get("OutTimestampReps","0")}i') 
        netstats.append(f'icmp_outtimestamps={icmp_stats.get("OutTimestamps","0")}i') 

        icmpmsg_stats = snmp_map['IcmpMsg:']['data'] if 'IcmpMsg:' in  snmp_map else {} 
        netstats.append(f'icmpmsg_intype3={icmpmsg_stats.get("InType3","0")}i')
        netstats.append(f'icmpmsg_outtype3={icmpmsg_stats.get("OutType3","0")}i')



        ip_stats = snmp_map['Ip:']['data'] if 'Ip:' in  snmp_map else {} 
        netstats.append(f'ip_defaultttl={ip_stats.get("DefaultTTL","0")}i')
        netstats.append(f'ip_forwarding={ip_stats.get("Forwarding","0")}i') 
        netstats.append(f'ip_forwdatagrams={ip_stats.get("ForwDatagrams","0")}i')
        netstats.append(f'ip_fragcreates={ip_stats.get("FragCreates","0")}i')
        netstats.append(f'ip_fragfails={ip_stats.get("FragFails","0")}i')
        netstats.append(f'ip_fragoks={ip_stats.get("FragOKs","0")}i')
        netstats.append(f'ip_inaddrerrors={ip_stats.get("InAddrErrors","0")}i')
        netstats.append(f'ip_indelivers={ip_stats.get("InDelivers","0")}i')
        netstats.append(f'ip_indiscards={ip_stats.get("InDiscards","0")}i')
        netstats.append(f'ip_inhdrerrors={ip_stats.get("InHdrErrors","0")}i')
        netstats.append(f'ip_inreceives={ip_stats.get("InReceives","0")}i')
        netstats.append(f'ip_inunknownprotos={ip_stats.get("InUnknownProtos","0")}i')
        netstats.append(f'ip_outdiscards={ip_stats.get("OutDiscards","0")}i')
        netstats.append(f'ip_outnoroutes={ip_stats.get("OutNoRoutes","0")}i')
        netstats.append(f'ip_outrequests={ip_stats.get("OutRequests","0")}i')
        netstats.append(f'ip_reasmfails={ip_stats.get("ReasmFails","0")}i')
        netstats.append(f'ip_reasmoks={ip_stats.get("ReasmOKs","0")}i')
        netstats.append(f'ip_reasmreqds={ip_stats.get("ReasmReqds","0")}i')
        netstats.append(f'ip_reasmtimeout={ip_stats.get("ReasmTimeout","0")}i')

        tcp_stats = snmp_map['Tcp:']['data'] if 'Tcp:' in  snmp_map else {}
        netstats.append(f'tcp_activeopens={tcp_stats.get("ActiveOpens","0")}i')
        netstats.append(f'tcp_attemptfails={tcp_stats.get("AttemptFails","0")}i')
        netstats.append(f'tcp_currestab={tcp_stats.get("CurrEstab","0")}i')
        netstats.append(f'tcp_estabresets={tcp_stats.get("EstabResets","0")}i')
        netstats.append(f'tcp_incsumerrors={tcp_stats.get("InCsumErrors","0")}i')
        netstats.append(f'tcp_inerrs={tcp_stats.get("InErrs","0")}i')
        netstats.append(f'tcp_insegs={tcp_stats.get("InSegs","0")}i')
        netstats.append(f'tcp_maxconn={tcp_stats.get("MaxConn","0")}i')
        netstats.append(f'tcp_outrsts={tcp_stats.get("OutRsts","0")}i')
        netstats.append(f'tcp_outsegs={tcp_stats.get("OutSegs","0")}i')
        netstats.append(f'tcp_passiveopens={tcp_stats.get("PassiveOpens","0")}i')
        netstats.append(f'tcp_retranssegs={tcp_stats.get("RetransSegs","0")}i')
        netstats.append(f'tcp_rtoalgorithm={tcp_stats.get("RtoAlgorithm","0")}i')
        netstats.append(f'tcp_rtomax={tcp_stats.get("RtoMax","0")}i')
        netstats.append(f'tcp_rtomin={tcp_stats.get("RtoMin","0")}i')

        udp_stats = snmp_map['Udp:']['data'] if 'Udp:' in  snmp_map else {}
        netstats.append(f'udp_ignoredmulti={udp_stats.get("IgnoredMulti","0")}i')
        netstats.append(f'udp_incsumerrors={udp_stats.get("InCsumErrors","0")}i')
        netstats.append(f'udp_indatagrams={udp_stats.get("InDatagrams","0")}i')
        netstats.append(f'udp_inerrors={udp_stats.get("InErrors","0")}i')
        netstats.append(f'udp_noports={udp_stats.get("NoPorts","0")}i')
        netstats.append(f'udp_outdatagrams={udp_stats.get("OutDatagrams","0")}i')
        netstats.append(f'udp_rcvbuferrors={udp_stats.get("RcvbufErrors","0")}i')
        netstats.append(f'udp_sndbuferrors={udp_stats.get("SndbufErrors","0")}i')

        udplite_stats = snmp_map['UdpLite:']['data'] if 'UdpLite:' in  snmp_map else {}
        netstats.append(f'udplite_ignoredmulti={udplite_stats.get("IgnoredMulti","0")}i')
        netstats.append(f'udplite_incsumerrors={udplite_stats.get("InCsumErrors","0")}i')
        netstats.append(f'udplite_indatagrams={udplite_stats.get("InDatagrams","0")}i')
        netstats.append(f'udplite_inerrors={udplite_stats.get("InErrors","0")}i')
        netstats.append(f'udplite_noports={udplite_stats.get("NoPorts","0")}i')
        netstats.append(f'udplite_outdatagrams={udplite_stats.get("OutDatagrams","0")}i')
        netstats.append(f'udplite_rcvbuferrors={udplite_stats.get("RcvbufErrors","0")}i')
        netstats.append(f'udplite_sndbuferrors={udplite_stats.get("SndbufErrors","0")}i')
        network.append(f'net,source={source},host={hostname},interface=all {",".join(netstats)} {nowSeconds}000000000')
        return network


    def collect(self, source):
        payload = []
        try:
            now = time.time()
            nowSeconds = int(now)
            stat = self.read_proc('/proc/stat')
            hostname = socket.gethostname()
            payload.extend(self.collect_cpu(source, hostname, nowSeconds, stat))
            payload.extend(self.collect_kernel(source, hostname, nowSeconds, stat))
            payload.extend(self.collect_process_stats(source, hostname, nowSeconds))
            payload.extend(self.collect_mem(source, hostname, nowSeconds))
            payload.extend(self.collect_diskio(source, hostname, nowSeconds))
            payload.extend(self.collect_net(source, hostname, nowSeconds))
            payload.extend(self.collect_system(source, hostname, nowSeconds, stat))
            payload.extend(self.collect_disk(source, hostname, nowSeconds))
            
        except:
            log.error(f'Os Collection failed')
            traceback.print_exc()


        return payload


if __name__ == '__main__':
    osMeter = OsMeter()
    payload = osMeter.collect('test')
    body = "\n".join(payload)
    total = len(body)
    print(body)
    print(f'total {total}')
