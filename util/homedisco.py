import os, sys, imp, cStringIO
from disco.netstring import decode_netstring_fd
from disco.core import Job, result_iterator

def import_disco_worker():
        global disco_worker
        path = None
        for p in sys.path:
                path = p + "/disco-worker"
                if os.path.exists(path):
                        break
        else:
                raise Exception("disco-worker not found. Check your PYTHONPATH.")
        desc = [x for x in imp.get_suffixes() if x[0] == ".py"][0]
        os.environ["DISCO_ROOT"] = "./"
        disco_worker = imp.load_module("disco-worker", file(path), path, desc)

class MsgStream:
        def __init__(self):
                self.out = []
        def write(self, msg):
                if msg.startswith("**<OUT>"):
                        addr = msg.split()[-1]
                        fname = "/".join(addr.split("/")[-2:])
                        if addr.startswith("chunk://"):
                                self.out.append("chunkfile://data/" + fname)
                        else:
                                self.out.append("file://data/" + fname)
                print msg,

class DummyDisco:
        def request(*args, **kwargs):
                return "job started"

class HomeDisco:
        
        def __init__(self, mode, partition = "0"):
                self.mode = mode
                self.partition = partition
        
        def new_job(self, *args, **kwargs):
                job = Job(DummyDisco(), **kwargs)
                req = decode_netstring_fd(cStringIO.StringIO(job.msg))

                argv_backup = sys.argv[:]
                out_backup = sys.stderr
                sys.argv = ["", "", "", "localhost", "", self.partition]
                sys.argv += kwargs["input"]
                disco_worker.job_name = job.name

                sys.stderr = out = MsgStream()
                try:
                        if self.mode == "map":
                                disco_worker.op_map(req)
                        elif self.mode == "reduce":
                                disco_worker.op_reduce(req)
                        else:
                                raise "Unknown mode: %s "\
                                      "(must be 'map' or 'reduce')"\
                                        % self.mode
                finally:
                        sys.argv = argv_backup
                        sys.stderr = out_backup
                return out.out

import_disco_worker()

if __name__ == "__main__":

        def fun_map(e, params):
                return [(e, e)]
        
        def fun_reduce(iter, out, params):
                for k, v in iter:
                        out.add("red:" + k, v)
        
        f = file("homedisco-test", "w")
        print >> f, "dog\ncat\npossum"
        f.close()

        map_hd = HomeDisco("map")
        reduce_hd = HomeDisco("reduce")
        
        res = map_hd.new_job(name = "homedisco",
                             input = ["homedisco-test"],
                             map = fun_map,
                             reduce = fun_reduce)
        
        res = reduce_hd.new_job(name = "homedisco",
                                input = res,
                                map = fun_map,
                                reduce = fun_reduce)

        for k, v in result_iterator(res):
                print "KEY", k, "VALUE", v

