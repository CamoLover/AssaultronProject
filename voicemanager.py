"""
VoiceManager - Complete voice system management for Assaultron
Handles xVAsynth server startup, model loading, and voice synthesis
"""

import subprocess
import time
import json
import requests
import threading
import os
import pygame
from pathlib import Path
from datetime import datetime


class VoiceManager:
    def __init__(self, logger=None):
        """Initialize VoiceManager with xVAsynth configuration"""
        self.logger = logger or self._create_default_logger()
        
        # Server configuration
        self.server_url = "http://localhost:8008"
        self.server_process = None
        self.server_running = False
        
        # Model configuration
        self.model_loaded = False
        self.model_path = Path("Content/xVAsynth/resources/app/models/fallout4")
        self.model_file = "f4_robot_assaultron.json"
        self.model_info = None
        
        # Voice synthesis configuration
        self.audio_output_dir = Path("audio_output")
        self.audio_output_dir.mkdir(exist_ok=True)
        
        # Status tracking
        self.is_initialized = False
        self.last_synthesis_file = None
        self.is_playing = False
        self.playback_start_time = None

        # Audio playback
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        
        self.log("VoiceManager initialized")
    
    def _create_default_logger(self):
        """Create a default logger if none provided"""
        import logging
        logger = logging.getLogger('VoiceManager')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s] [%(name)s] %(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def log(self, message, level="INFO"):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [VOICE] {level}: {message}")
        if hasattr(self.logger, 'log_event'):
            self.logger.log_event(message, "VOICE")
    
    def start_server(self):
        """Start the xVAsynth server"""
        if self.server_running:
            self.log("Server already running")
            return True
        
        try:
            # Path to xVAsynth server executable - exact path from your working command
            app_dir = Path("Content/xVAsynth/resources/app")
            server_exe = app_dir / "cpython_gpu" / "server.exe"

            # If the port is already in use, try to free it first
            try:
                freed = self._free_port_if_occupied()
                if not freed:
                    self.log("Port 8008 is occupied and could not be freed", "ERROR")
                    return False
            except Exception as e:
                self.log(f"Error while trying to free port: {e}", "WARN")
            
            if not app_dir.exists():
                self.log(f"App directory not found: {app_dir}", "ERROR")
                return False
            
            if not server_exe.exists():
                self.log(f"Server executable not found: {server_exe}", "ERROR")
                return False
            
            self.log("Starting xVAsynth server...")

            # Start server process using the resolved executable path. Using the
            # full path avoids Windows failing to locate the executable when a
            # relative './' prefix is used.
            self.log(f"Starting server from directory: {app_dir}")
            server_cmd = str(server_exe.resolve())
            self.log(f"Server command: {server_cmd} (cwd={app_dir})")

            def _tail_stream(stream, prefix):
                try:
                    for line in iter(stream.readline, b""):
                        if not line:
                            break
                        try:
                            decoded = line.decode('utf-8', errors='ignore').rstrip()
                        except:
                            decoded = str(line)
                        self.log(f"[{prefix}] {decoded}")
                except Exception as e:
                    self.log(f"Error tailing {prefix}: {e}", "WARN")

            def _start_process(cmd, cwd):
                try:
                    proc = subprocess.Popen(
                        [cmd],
                        cwd=str(cwd),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        shell=False
                    )

                    # Start reader threads for stdout/stderr
                    try:
                        t_out = threading.Thread(target=_tail_stream, args=(proc.stdout, 'SERVER_OUT'), daemon=True)
                        t_err = threading.Thread(target=_tail_stream, args=(proc.stderr, 'SERVER_ERR'), daemon=True)
                        t_out.start()
                        t_err.start()
                    except Exception:
                        pass

                    return proc
                except Exception as e:
                    self.log(f"Popen failed for command: {cmd} cwd={cwd} - {e}", "ERROR")
                    return None

            # Try primary start (absolute path, cwd=app_dir)
            self.server_process = _start_process(server_cmd, app_dir)

            # If starting the absolute path immediately failed, try fallback
            if not self.server_process:
                # Try launching from the cpython_cpu folder using the exe name
                cpu_dir = app_dir / 'cpython_gpu'
                if cpu_dir.exists():
                    self.log(f"Primary start failed; attempting fallback in {cpu_dir}")
                    self.server_process = _start_process(server_exe.name, cpu_dir)
                else:
                    self.log(f"Fallback gpu dir not found: {cpu_dir}", "ERROR")
            
            # Wait for server to start (up to 45 seconds - xVAsynth takes time to initialize)
            for i in range(45):
                time.sleep(1)
                if self.check_server_status():
                    # TCP port is open; proceed. `load_model` includes
                    # retries and a raw-socket fallback to handle transient
                    # HTTP problems, so we don't block here on HTTP probes.
                    self.server_running = True
                    self.log("xVAsynth server TCP port open; proceeding to model load")
                    return True
                    
                # Check if process died
                if self.server_process.poll() is not None:
                    self.log(f"Server process exited with code: {self.server_process.returncode}", "ERROR")
                    try:
                        stdout, stderr = self.server_process.communicate(timeout=2)
                        if stdout:
                            output = stdout.decode('utf-8', errors='ignore')
                            self.log(f"Server stdout: {output[-500:]}", "ERROR")
                        if stderr:
                            error_output = stderr.decode('utf-8', errors='ignore')
                            self.log(f"Server stderr: {error_output[-500:]}", "ERROR")
                    except:
                        pass
                    return False
                
                # Only log every 5 seconds to avoid spam
                if (i + 1) % 5 == 0:
                    self.log(f"Waiting for server to start... ({i+1}/45)")
            
            self.log("Server failed to start within timeout", "ERROR")
            
            # Try to get error output from server if still running
            if self.server_process and self.server_process.poll() is None:
                self.log("Server process still running but not responding", "ERROR")
            elif self.server_process:
                try:
                    stdout, stderr = self.server_process.communicate(timeout=2)
                    if stdout:
                        output = stdout.decode('utf-8', errors='ignore')
                        self.log(f"Server final output: {output[-500:]}", "ERROR")
                except:
                    pass
            
            return False
            
        except Exception as e:
            self.log(f"Failed to start server: {e}", "ERROR")
            return False
    
    def check_server_status(self):
        """Check if xVAsynth server is responding"""
        try:
            # xVAsynth server sometimes returns empty responses but is still working
            # Try all resolved addresses for 'localhost' (IPv4/IPv6) to avoid
            # cases where 'localhost' resolves to ::1 but we try an IPv4 socket.
            import socket

            try:
                addrs = socket.getaddrinfo('localhost', 8008, 0, socket.SOCK_STREAM)
            except Exception:
                addrs = []
            if not addrs:
                self.log("No addresses resolved for localhost", "WARN")

            for family, socktype, proto, canonname, sockaddr in addrs:
                try:
                    sock = socket.socket(family, socktype, proto)
                    sock.settimeout(2)
                    result = sock.connect_ex(sockaddr)
                    sock.close()
                except Exception as e:
                    result = 1

                # If TCP connect succeeded, consider server ready (port open)
                if result == 0:
                    return True

            # If no addresses connected successfully, server isn't up yet
            return False
        except:
            return False

    def find_open_address(self):
        """Return the first IP address string for which the server port is open, or None."""
        try:
            import socket
            addrs = socket.getaddrinfo('localhost', 8008, 0, socket.SOCK_STREAM)
        except Exception:
            return None

        for family, socktype, proto, canonname, sockaddr in addrs:
            try:
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(1)
                result = sock.connect_ex(sockaddr)
                sock.close()
            except Exception:
                result = 1

            if result == 0:
                ip = sockaddr[0]
                return ip
        return None

    def _free_port_if_occupied(self):
        """If port 8008 is occupied, try graceful shutdown via /stopServer or kill the owning process on Windows.

        Returns True if port is free or was freed, False otherwise.
        """
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 8008))
            sock.close()
        except Exception:
            result = 1

        if result != 0:
            # Port not in use
            return True

        # Port is in use. Try graceful shutdown via HTTP if possible
        try:
            try:
                requests.post(f"{self.server_url}/stopServer", timeout=2)
                time.sleep(1)
            except Exception:
                pass

            # Re-check
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 8008))
            sock.close()
            if result != 0:
                return True
        except Exception:
            pass

        # Still occupied -- attempt to find and kill process on Windows using netstat and taskkill
        try:
            if os.name == 'nt':
                output = subprocess.check_output(['netstat', '-ano'], stderr=subprocess.STDOUT, text=True)
                lines = output.splitlines()
                pids = set()
                for line in lines:
                    if ':8008' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            try:
                                int(pid)
                                pids.add(pid)
                            except:
                                pass

                for pid in pids:
                    try:
                        self.log(f"Attempting to kill process using port 8008: PID={pid}")
                        subprocess.check_call(['taskkill', '/PID', pid, '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        time.sleep(0.5)
                    except Exception as e:
                        self.log(f"Failed to kill PID {pid}: {e}", "WARN")

                # Final check
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', 8008))
                sock.close()
                return result != 0
            else:
                # On non-Windows systems, just return False (user must free port)
                return False
        except Exception as e:
            self.log(f"Error while trying to free port: {e}", "WARN")
            return False
    
    def stop_server(self):
        """Stop the xVAsynth server"""
        try:
            if self.server_process:
                # Try graceful shutdown first
                try:
                    requests.post(f"{self.server_url}/stopServer", timeout=5)
                    time.sleep(2)
                except:
                    pass
                
                # Force terminate if still running
                if self.server_process.poll() is None:
                    self.server_process.terminate()
                    time.sleep(2)
                    
                    # Force kill if still running
                    if self.server_process.poll() is None:
                        self.server_process.kill()
                
                self.server_process = None
                self.log("xVAsynth server stopped")
            
            self.server_running = False
            self.model_loaded = False
            self.is_initialized = False
            
        except Exception as e:
            self.log(f"Error stopping server: {e}", "ERROR")
    
    def load_model_config(self):
        """Load Assaultron model configuration from JSON file"""
        try:
            model_json_path = self.model_path / self.model_file
            
            if not model_json_path.exists():
                self.log(f"Model file not found: {model_json_path}", "ERROR")
                return False
            
            with open(model_json_path, 'r', encoding='utf-8') as f:
                self.model_info = json.load(f)
            
            self.log(f"Model config loaded: {self.model_info.get('games', [{}])[0].get('voiceName', 'Unknown')}")
            return True
            
        except Exception as e:
            self.log(f"Failed to load model config: {e}", "ERROR")
            return False
    
    def load_model(self):
        """Load the Assaultron voice model into xVAsynth"""
        if not self.server_running:
            self.log("Server not running, cannot load model", "ERROR")
            return False

        if not self.model_info:
            if not self.load_model_config():
                return False

        try:
            self.log("Loading Assaultron voice model...")

            # Correct model path based on xVAsynth analysis
            # Server expects path WITHOUT .pt extension and adds it automatically
            model_path = "models/fallout4/f4_robot_assaultron"

            payload = {
                "modelType": "xVAPitch",
                "model": model_path,
                "pluginsContext": "{}",
                "base_lang": "en"
            }

            self.log(f"Loading model: {model_path}")

            # Send model load request with retries because the server may
            # briefly close connections while finishing startup.
            attempts = 6
            wait = 1.0
            response = None

            # Prefer posting to the specific open IP (IPv4/IPv6) if available
            open_ip = self.find_open_address()
            if open_ip:
                if ':' in open_ip:
                    target_base = f"http://[{open_ip}]:8008"
                else:
                    target_base = f"http://{open_ip}:8008"
            else:
                target_base = self.server_url

            headers = {"Content-Type": "application/json", "Connection": "close"}

            for attempt in range(1, attempts + 1):
                try:
                    data = json.dumps(payload)
                    url = f"{target_base}/loadModel"
                    self.log(f"Posting to {url} (attempt {attempt})")
                    response = requests.post(url, data=data, headers=headers, timeout=30)
                    self.log(f"Model load request sent (attempt {attempt}), response code: {response.status_code}")
                    break
                except Exception as e:
                    self.log(f"Model load attempt {attempt} failed: {e}", "WARN")
                    # If server closed connection immediately, try again after a pause
                    if attempt < attempts:
                        time.sleep(wait)
                        wait *= 1.6
                    else:
                        # Final fallback: attempt a raw socket POST (curl-like)
                        try:
                            self.log("All requests attempts failed; trying raw socket POST fallback", "WARN")

                            def _socket_post(host_ip, payload_str):
                                import socket
                                # Resolve address info
                                try:
                                    infos = socket.getaddrinfo(host_ip, 8008, 0, socket.SOCK_STREAM)
                                except Exception as e:
                                    self.log(f"socket.getaddrinfo failed: {e}", "ERROR")
                                    return False, None

                                for family, socktype, proto, canonname, sockaddr in infos:
                                    try:
                                        sock = socket.socket(family, socktype, proto)
                                        sock.settimeout(10)
                                        sock.connect(sockaddr)

                                        body = payload_str.encode('utf-8')
                                        req_lines = []
                                        req_lines.append('POST /loadModel HTTP/1.1')
                                        req_lines.append(f'Host: {host_ip}:8008')
                                        req_lines.append('User-Agent: curl/7.79.1')
                                        req_lines.append('Accept: */*')
                                        req_lines.append('Content-Type: application/json')
                                        req_lines.append(f'Content-Length: {len(body)}')
                                        req_lines.append('Connection: close')
                                        req = '\r\n'.join(req_lines) + '\r\n\r\n'
                                        sock.sendall(req.encode('utf-8') + body)

                                        # Read response
                                        resp = b''
                                        while True:
                                            chunk = sock.recv(4096)
                                            if not chunk:
                                                break
                                            resp += chunk
                                        sock.close()
                                        # Parse status line
                                        try:
                                            first_line = resp.split(b'\r\n', 1)[0].decode('utf-8', errors='ignore')
                                        except:
                                            first_line = ''
                                        return True, first_line
                                    except Exception as e:
                                        self.log(f"Socket attempt to {sockaddr} failed: {e}", "WARN")
                                        try:
                                            sock.close()
                                        except:
                                            pass
                                        continue
                                return False, None

                            post_host = open_ip if open_ip else 'localhost'
                            ok, status_line = _socket_post(post_host, data)
                            if ok:
                                self.log(f"Raw socket POST succeeded, status: {status_line}")
                            else:
                                self.log("Raw socket POST fallback failed", "ERROR")
                            # Final fallback: try invoking system `curl` to mimic
                            # exactly the command that works for you.
                            try:
                                curl_cmd = [
                                    'curl', '-sS', '-X', 'POST', f"{self.server_url}/loadModel",
                                    '-H', 'Content-Type: application/json', '-d', data
                                ]
                                self.log(f"Attempting subprocess curl fallback: {' '.join(curl_cmd)}")
                                proc = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
                                self.log(f"curl exit {proc.returncode}, stdout: {proc.stdout[:500]}, stderr: {proc.stderr[:500]}")
                            except Exception as e3:
                                self.log(f"curl fallback failed: {e3}", "ERROR")
                        except Exception as e2:
                            self.log(f"Raw socket POST fallback raised: {e2}", "ERROR")
                        raise

            # Wait for model to load (xVAsynth may take a while on CPU).
            # Poll by attempting a small synthesis until success or timeout.
            self.log("Waiting for model to load (polling for readiness)...")

            # Polling configuration
            total_timeout = 120  # seconds
            poll_interval = 5    # seconds
            start_time = time.time()

            # Use the same target_base we posted to (if available) when testing
            test_base = target_base if 'target_base' in locals() else self.server_url

            while True:
                elapsed = time.time() - start_time
                if elapsed > total_timeout:
                    self.log(f"Model did not become ready within {total_timeout} seconds", "ERROR")
                    return False

                try:
                    if self.test_model(server_base=test_base):
                        self.model_loaded = True
                        self.log("Assaultron voice model loaded successfully!")
                        return True
                except Exception as e:
                    self.log(f"Error during model test attempt: {e}", "WARN")

                time.sleep(poll_interval)

        except Exception as e:
            self.log(f"Failed to load model: {e}", "ERROR")
            return False
    
    def test_model(self, server_base=None):
        """Test if model is loaded by attempting a quick synthesis"""
        try:
            # Use absolute path so xVAsynth server can find the directory
            test_output = str(self.audio_output_dir.resolve() / "test.wav")
            
            # Embedding vector for Assaultron voice model
            base_emb = "-0.04141310348721414,-0.06264781161885837,-0.009893516568087665,0.004431465048300792,0.0197084597873919,-0.02504097404568617,0.03896980891646497,0.011261365971724193,0.030373606565890127,-0.03668549274704579,0.007043571825275203,0.042889138587333,0.06884410155230555,0.0948248897390119,0.004462419471659311,-0.012933785204197568,0.038499683414682226,0.028057241081741863,-0.054789068915977554,-0.019294065993343445,0.032299037428637004,0.01943167968219596,0.0277703470943881,0.008334622877963077,-0.0204040042229061,0.002083010988857934,0.021861803786154706,-0.05575870648668758,0.031887964124727095,-0.016493192871888003,0.03696166871693627,0.005801141269079507,-0.054017134460395785,0.014095563985486888,-0.0535404777860847,-0.004288397425061077,-0.011206367009937573,-0.04678877998657267,-0.04224884238672154,-0.04032117587610565,-0.05300952108769581,0.031355311114597946,0.0064718217976139246,0.073070895633307,0.03907466972054078,0.044020538218319416,-0.06913498101820206,0.04375158186102735,-0.06942112230021379,-0.028204646260088215,-0.04431328651142018,-0.0127403451637104,-0.04030410511868781,-0.018865757433653426,-0.05924102927333322,0.0036518346419927247,0.01899502462966384,0.01641203935563179,0.07062690865633817,-0.02360071868089766,0.022430224452521005,-0.05601849737737713,0.009028535743364676,0.007017398269140521,-0.042817008585251615,0.03986586771648506,0.003244350579515067,-0.02356682547191479,-0.062491667103664626,0.04269033366942714,0.02592908234158852,-0.037676204493718925,-0.03280210331210802,0.04244666129093746,-0.05304856678663657,0.0030822648189094822,-0.04221125770809835,-0.05611751755249911,0.014891362394776259,0.0180648667055407,0.0012095455794819986,-0.0010088664165433091,-0.01068097727718474,0.07080326794550337,0.08602111362691583,0.0026097792442669773,-0.011003180288565183,0.0636280831912982,-0.019702864248819396,0.011929258744328701,-0.0006492820855406728,-0.06490375557593231,-0.06428098485901437,0.012923152284327383,0.05946176942309429,-0.027278540543569575,-0.0008773312787023575,0.04042583989814437,-0.05911436021841806,0.011810176192927334,0.04690386756355393,0.02417449165810028,-0.04380513640955604,-0.03210011641655503,-0.0452087946428821,-0.05574655388321342,-0.00919322527612355,-0.02692963022955469,0.04261740252118686,-0.061171267952384624,-0.021372246539926733,-0.025635177671010125,0.02431445847393881,-0.06219971090041358,0.02616120683800044,0.013440994049985954,0.02148948704767651,0.04975893080298756,0.03319090124669259,-0.014370421479568532,-0.005390361912853629,-0.06071490248472527,0.0035259453163297583,0.0284778769770316,-0.01042137300828472,-0.05741894669060049,0.08207124683620601,-0.01959627952701653,-0.044222460032023236,-0.03088471424516997,0.013789583702073914,0.01872053034683882,-0.06337755790044522,0.017963768355724007,-0.00768601264876609,-0.06511763207100589,-0.05601597455298078,0.0009993920958267745,0.025789873481824484,-0.003970622644530899,-0.06517209825587683,0.027534729500044264,-0.034273743982715855,-0.016003619321493495,0.017218906297910445,-0.0030898707958965975,0.008274813674908163,-0.010069639002001073,0.020922205262367835,-0.009025484010509963,0.05137356187634427,-0.017562705112203696,0.04980739559335955,-0.01617638111427619,-0.058127908678404214,0.012257558056795653,0.07751455819555397,0.05316594063208021,-0.12388520623589384,0.030799824511632323,-0.03816840665190127,-0.05039971292918098,-0.017198882158042796,0.05536174090129548,0.07594173478669135,-0.006661475140798107,0.054725528148741556,0.02521188250453822,-0.006281848987845441,0.06255616498147619,-0.015720460258056977,-0.0035667354618532238,-0.02487493085058743,0.059074002414427965,0.03610046387746416,-0.0056987822934953,-0.07814554902243204,-0.001125086367116231,-0.014599541013984857,-0.021929055564747803,0.008415844702916543,0.005716092235725858,-0.018729277344015107,0.05229183138701422,0.05475631645270462,-0.05577566246662674,-0.038473972986484396,0.026979638584728894,-0.09366494468573866,-0.08306307210747538,-0.010545415437608709,0.020443317326837507,0.0770345625050109,0.007709582571335662,0.011759920910819722,-0.05801661842470539,0.047826129092096256,0.023202413972065745,0.010967465007624843,-0.014360523973350766,-0.02907960833695613,-0.036327998547268835,0.01594350088271312,-0.026753001958774086,0.0314492679618556,0.09815294976378308,0.0014163269823821505,-0.050223126140391004,0.03214855879095608,-0.025164807805438234,-0.07068257412776865,-0.05768520153802017,0.06976194204441433,0.03924475388665652,0.06908157133850559,0.03846941870669353,0.051877158726083825,-0.013259729211932643,0.008649842107278628,-0.03559094879390865,-0.01598218714432984,-0.02747342464160817,-0.04383447893558007,-0.01827551249177838,0.012354999564885123,-0.01663628885530514,0.006175483035835425,-0.028078559300348412,-0.020828177604361654,-0.008645337003740837,0.007138649350210845,0.005499324730784608,0.039896782407344414,0.10450955570257943,0.00984409835040549,0.018413460361851576,0.002126183875965392,0.023506279511915133,-0.011763287922302218,0.0005075793642077015,0.0077204595837774195,-0.019793503921768017,0.02940829111873333,-0.014293231850827178,0.04318965489751306,-0.0480774254377546,0.04136698467030736,0.023411763542941933,-0.042039787862449884,0.00947594205329018,-0.0030860043994395923,0.015506735373617568,0.04399403737022959,0.08289867588158312,0.022333357125873962,-0.028244875925432508,0.016429133380056707,0.054443227384110976,-0.0515108017957416,0.06778584979474545,0.0006057115036849715,-0.056708767656879176,0.0628362305719277,0.009779272498894112,-0.0023545143104174433,-0.04800801101172793,-0.07734973902075454,-0.03602449028604214,0.03567800254978496,0.034197270805979604,-0.040816437774177254,0.008703518651102589,0.022028252075336964,-0.0415938606742641,0.03972635940038439,0.09635748521521174,0.014070984395371413,0.01227214452328867,-0.09475001358780367,0.021235109195474465,-0.021782820000602252,0.02649204359502243,0.06437021641638772,-0.004583319226592981,-0.01986938435785023,-0.027010519440879982,0.04455232912481859,0.0607588745910546,-0.08578989256558747,0.03188484232744266,-0.04654071913582498,-0.05058052544963771,0.1462401501063643,-0.08104207790617284,0.05242066602383194,0.09758897562479152,0.003667611777300722,0.04532572427957223,0.07893792321455889,0.007804954623711166,0.03246927796060155,-0.07110405488517776,0.005019943377699551,-0.07687626046867206,-0.047155525214199356,0.0022281700600207577,-0.024901406975976863,-0.08840684265155216,0.03778957309008672,0.011140980494834871,-0.006989547314427408,-0.01945731383226491,-0.03411471541441077,0.048739581593665586,-0.13881510329143754,0.04037931795906404,0.1141204787739392,-0.05266589552549453,-0.08436076953236399,0.021568092581783906,-0.022252840227306947,-0.029199876075867437,0.06508748509503644,0.037151341021446314,0.004042465094494998,0.01020428093156154,0.04349330724377571,-0.014137525687491978,0.008101273129858748,0.015928811918550716,-0.04418383331584005,-0.08103222849554029,-0.0382715406795514,-0.0014375236707314001,-0.05384260881692171,0.04291804549123707,0.02046805208725534,-0.0013900216595331906,-0.06865624980679874,0.007758140760164805,0.04401981210785693,0.0256849607163719,0.021481808969461967,0.008827832839572156,0.11440639236363873,-0.006436499979513585,0.007964550096497484,-0.07074560668191006,-0.06429555707065196,-0.017979423557147222,0.036029792326534624,-0.023239507301758718,-0.03573990860504323,0.06005970966713182,0.028023924782936423,0.019336117786788863,0.01983697007807646,0.003765739767851332,-0.030881868926246232,0.07132344892055824,-0.02955966525367895,-0.017133256926799414,-0.04592337719453819,0.029483074707717733,-0.09826675031719537,0.013001378500999196,-0.05294574504910871,0.004635196110531731,0.04963825742617763,0.017034980075550273,0.037806761210206256,0.04232036152148041,0.012094870999950713,0.005204215365289389,-0.019584790077401677,0.03185024219243948,-0.011107684686631447,0.020483255707498253,0.057494086245524476,-0.06704135663036642,-0.033480213617841745,0.07719388475705838,-0.0062528905307709486,0.0006969927103611957,-0.01522777279601071,-0.017358632267508976,-0.019484200343240755,-0.057102405048649885,-0.03501504728949934,0.07019221545036496,0.07572564110159874,-0.024650863086772636,-0.0875906837654525,-0.01985601199226823,0.07298104664118125,0.037413348427748884,0.0011616072775911422,0.09168200387523093,0.008952356823007492,0.04636509905986745,0.039468552716525974,-0.019885230708088536,-0.028423968955456954,-0.01951354887418786,-0.02601983638255504,-0.005254610456678825,-0.030798536428282487,-0.03558343456223093,-0.05118288035536635,0.010503973158534038,-0.04067756450767147,-0.031071714342346995,0.024844086676803902,-0.018541790460685978,0.012702065153179913,0.04500884077800759,-0.07751070939261338,-0.044065682490452604,-0.016021165553583756,0.013731671865539752,-0.003769310128549912,0.05342676130862072,-0.002239083660242613,-0.05029611360153247,-0.05392139119192444,0.038098281112917014,0.024988388036506187,0.002969041892607369,0.018417823776715143,-0.056067326748422505,0.018319390378470916,0.012477484189479714,-0.05982122306936774,0.023933992456195166,-0.03407038854242399,-0.06582458114958015,-0.0021704752221482788,-0.02247413349185332,-0.05015290952448188,-0.01263468959900663,-0.0097404211937201,0.07768376068822269,0.03211997561397609,-0.01810258243168736,0.02246928176690086,-0.08787336264704836,-0.03952167114114453,-0.008428809718240922,-0.0351996633770137,-0.006409297949521091,0.05705444000918291,-0.06592274682018263,-0.05209530979908746,0.04655744082390748,-0.0035241836477984314,0.0011544361202360364,0.04716583800598465,0.02023317171802648,-0.006477349283519793,0.02618343754398541,0.03356296106056984,0.032218376929261563,0.0023530563791202145,-0.0006311093998976622,-0.005960396578553501,-0.07214969717736902,0.0007085758478406832,0.03547185439423754,-0.015053624147318758,0.03343241218605946,0.0033105846021749914,0.051412301555532836,0.006784216334726173,0.0025287374583685632,-0.033035582164302475,-0.038403945364828766,-0.019868204212704358,-0.04907445853640293,-0.03050950593475638,-0.01666445615259802,-0.0014492251289554808,0.042815139902562936,0.0495132369727924,-0.028810246854595,0.07967374460964367,0.022885093826736355,0.053263594267954094,-0.006237034474906981,0.05050630633044859,0.027708918562737002,-0.016718161078611526,-0.01643435411950059,-0.05347275952326841,0.0381264361263863,0.004416858503426388,0.03891825105930711,0.035645528150529696,0.014044698269572109,-0.008845668097223851,0.05951393087362421,0.028155180874505446,-0.01180434488171535,-0.045943127431232356,-0.07590700326294735,0.016165692895120973,0.04329341438052984,0.0046882159226540885,0.03208396220900889,-0.018347399431714338,-0.0170413568751679,-0.0006521148678012663,-0.11865089024449217"
            
            test_payload = {
                "sequence": "System test. if you hear this, it's working.",
                "outfile": test_output,
                "instance_index": 0,
                "base_lang": "en",
                "pluginsContext": "{}",
                "editor_data": "{}",
                "base_emb": base_emb,
                "vocoder": "n/a",
                "modelType": "xVAPitch",
                "pace": 1.0
            }
            
            base = server_base if server_base else self.server_url
            
            try:
                response = requests.post(
                    f"{base}/synthesize",
                    json=test_payload,
                    timeout=30
                )
            except Exception as e:
                # Server may crash due to xVAsynth bug but still write file before crashing
                pass
            
            # Wait for synthesis to complete (file may still be written despite error)
            time.sleep(3)
            
            # Check if file was created with .wav extension
            test_file = Path(test_output)
            
            if test_file.exists():
                # Try to play it first before deleting
                try:
                    self.play_audio(str(test_file))
                    # Give pygame time to release the file handle
                    time.sleep(0.5)
                except Exception as e:
                    pass
                
                # Clean up test file after playing
                try:
                    test_file.unlink()
                except Exception as e:
                    # If file is still locked, it's okay - don't fail the test
                    pass
                return True
            else:
                self.log(f"Test file not created: {test_file}", "ERROR")
                return False
            
        except Exception as e:
            self.log(f"Model test failed: {e}", "ERROR")
            return False
    
    def initialize_complete_system(self):
        """Initialize the complete voice system (server + model)"""
        self.log("=" * 60)
        self.log("INITIALIZING ASSAULTRON VOICE SYSTEM")
        self.log("=" * 60)
        
        try:
            # Step 1: Start server
            if not self.start_server():
                return {"success": False, "error": "Failed to start xVAsynth server"}
            
            # Step 2: Load model configuration
            if not self.load_model_config():
                return {"success": False, "error": "Failed to load model configuration"}
            
            # Step 3: Load model into server
            if not self.load_model():
                return {"success": False, "error": "Failed to load Assaultron voice model"}
            
            # Step 4: Final verification
            if not self.verify_system():
                return {"success": False, "error": "System verification failed"}
            
            self.is_initialized = True
            self.log("=" * 60)
            self.log("ASSAULTRON VOICE SYSTEM READY!")
            self.log("=" * 60)
            
            return {
                "success": True,
                "message": "Assaultron voice system online - all systems operational",
                "model": self.model_info.get('games', [{}])[0].get('voiceName', 'Unknown'),
                "server_url": self.server_url
            }
            
        except Exception as e:
            return {"success": False, "error": f"Voice system initialization failed: {e}"}
    
    def verify_system(self):
        """Final verification that everything is working"""
        try:
            # Server just loaded the model successfully, so it's ready
            # Skip the synthesis test because xVAsynth has a bug with editor_data handling
            # that causes UnboundLocalError during synthesis, even though files are created
            
            # Just verify the server is still responding and model is marked loaded
            time.sleep(1)
            
            if not self.model_loaded:
                self.log("Verification failed: Model not marked as loaded", "WARN")
                return False
            
            # Model loaded successfully - system is ready
            return True
            
        except Exception as e:
            self.log(f"System verification error: {e}", "ERROR")
            return False
    
    def synthesize_voice(self, text, play_audio=True, filename=None):
        """
        Synthesize text to speech using loaded Assaultron model

        Args:
            text (str): Text to synthesize
            play_audio (bool): Whether to automatically play the audio
            filename (str): Optional custom filename (without extension)

        Returns:
            str: Path to generated audio file, or None if failed
        """
        if not self.is_initialized:
            self.log("Voice system not initialized", "ERROR")
            return None

        try:
            # Clean text for synthesis
            import re

            # Remove square brackets and their contents
            clean_text = re.sub(r'\[.*?\]', '', text)

            # SECURITY: Remove parentheses and their contents
            # This prevents the AI from adding stage directions or meta-commentary
            # that would be synthesized to speech
            # Example: "hello (pause for a bit) how are you?" → "hello how are you?"
            clean_text = re.sub(r'\([^)]*\)', '', clean_text)

            # Remove asterisks and stage directions (e.g., *looks around*)
            clean_text = re.sub(r'\*[^*]*\*', '', clean_text)

            # Clean up multiple spaces and strip
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            if not clean_text:
                self.log("No text to synthesize after cleaning", "WARN")
                return None
            
            # Generate filename
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"assaultron_voice_{timestamp}"
            
            output_path = self.audio_output_dir / f"{filename}.wav"
            
            self.log(f"Synthesizing: '{clean_text[:50]}{'...' if len(clean_text) > 50 else ''}'")
            
            # Prepare synthesis payload with absolute path and .wav extension
            output_filename = str(self.audio_output_dir.resolve() / (filename + ".wav"))
            payload = {
                "sequence": clean_text,
                "pluginsContext": "{}",
                "outfile": output_filename,
                "base_lang": "en",
                "editor_data": "{}",
                "base_emb": "-0.04141310348721414,-0.06264781161885837,-0.009893516568087665,0.004431465048300792,0.0197084597873919,-0.02504097404568617,0.03896980891646497,0.011261365971724193,0.030373606565890127,-0.03668549274704579,0.007043571825275203,0.042889138587333,0.06884410155230555,0.0948248897390119,0.004462419471659311,-0.012933785204197568,0.038499683414682226,0.028057241081741863,-0.054789068915977554,-0.019294065993343445,0.032299037428637004,0.01943167968219596,0.0277703470943881,0.008334622877963077,-0.0204040042229061,0.002083010988857934,0.021861803786154706,-0.05575870648668758,0.031887964124727095,-0.016493192871888003,0.03696166871693627,0.005801141269079507,-0.054017134460395785,0.014095563985486888,-0.0535404777860847,-0.004288397425061077,-0.011206367009937573,-0.04678877998657267,-0.04224884238672154,-0.04032117587610565,-0.05300952108769581,0.031355311114597946,0.0064718217976139246,0.073070895633307,0.03907466972054078,0.044020538218319416,-0.06913498101820206,0.04375158186102735,-0.06942112230021379,-0.028204646260088215,-0.04431328651142018,-0.0127403451637104,-0.04030410511868781,-0.018865757433653426,-0.05924102927333322,0.0036518346419927247,0.01899502462966384,0.01641203935563179,0.07062690865633817,-0.02360071868089766,0.022430224452521005,-0.05601849737737713,0.009028535743364676,0.007017398269140521,-0.042817008585251615,0.03986586771648506,0.003244350579515067,-0.02356682547191479,-0.062491667103664626,0.04269033366942714,0.02592908234158852,-0.037676204493718925,-0.03280210331210802,0.04244666129093746,-0.05304856678663657,0.0030822648189094822,-0.04221125770809835,-0.05611751755249911,0.014891362394776259,0.0180648667055407,0.0012095455794819986,-0.0010088664165433091,-0.01068097727718474,0.07080326794550337,0.08602111362691583,0.0026097792442669773,-0.011003180288565183,0.0636280831912982,-0.019702864248819396,0.011929258744328701,-0.0006492820855406728,-0.06490375557593231,-0.06428098485901437,0.012923152284327383,0.05946176942309429,-0.027278540543569575,-0.0008773312787023575,0.04042583989814437,-0.05911436021841806,0.011810176192927334,0.04690386756355393,0.02417449165810028,-0.04380513640955604,-0.03210011641655503,-0.0452087946428821,-0.05574655388321342,-0.00919322527612355,-0.02692963022955469,0.04261740252118686,-0.061171267952384624,-0.021372246539926733,-0.025635177671010125,0.02431445847393881,-0.06219971090041358,0.02616120683800044,0.013440994049985954,0.02148948704767651,0.04975893080298756,0.03319090124669259,-0.014370421479568532,-0.005390361912853629,-0.06071490248472527,0.0035259453163297583,0.0284778769770316,-0.01042137300828472,-0.05741894669060049,0.08207124683620601,-0.01959627952701653,-0.044222460032023236,-0.03088471424516997,0.013789583702073914,0.01872053034683882,-0.06337755790044522,0.017963768355724007,-0.00768601264876609,-0.06511763207100589,-0.05601597455298078,0.0009993920958267745,0.025789873481824484,-0.003970622644530899,-0.06517209825587683,0.027534729500044264,-0.034273743982715855,-0.016003619321493495,0.017218906297910445,-0.0030898707958965975,0.008274813674908163,-0.010069639002001073,0.020922205262367835,-0.009025484010509963,0.05137356187634427,-0.017562705112203696,0.04980739559335955,-0.01617638111427619,-0.058127908678404214,0.012257558056795653,0.07751455819555397,0.05316594063208021,-0.12388520623589384,0.030799824511632323,-0.03816840665190127,-0.05039971292918098,-0.017198882158042796,0.05536174090129548,0.07594173478669135,-0.006661475140798107,0.054725528148741556,0.02521188250453822,-0.006281848987845441,0.06255616498147619,-0.015720460258056977,-0.0035667354618532238,-0.02487493085058743,0.059074002414427965,0.03610046387746416,-0.0056987822934953,-0.07814554902243204,-0.001125086367116231,-0.014599541013984857,-0.021929055564747803,0.008415844702916543,0.005716092235725858,-0.018729277344015107,0.05229183138701422,0.05475631645270462,-0.05577566246662674,-0.038473972986484396,0.026979638584728894,-0.09366494468573866,-0.08306307210747538,-0.010545415437608709,0.020443317326837507,0.0770345625050109,0.007709582571335662,0.011759920910819722,-0.05801661842470539,0.047826129092096256,0.023202413972065745,0.010967465007624843,-0.014360523973350766,-0.02907960833695613,-0.036327998547268835,0.01594350088271312,-0.026753001958774086,0.0314492679618556,0.09815294976378308,0.0014163269823821505,-0.050223126140391004,0.03214855879095608,-0.025164807805438234,-0.07068257412776865,-0.05768520153802017,0.06976194204441433,0.03924475388665652,0.06908157133850559,0.03846941870669353,0.051877158726083825,-0.013259729211932643,0.008649842107278628,-0.03559094879390865,-0.01598218714432984,-0.02747342464160817,-0.04383447893558007,-0.01827551249177838,0.012354999564885123,-0.01663628885530514,0.006175483035835425,-0.028078559300348412,-0.020828177604361654,-0.008645337003740837,0.007138649350210845,0.005499324730784608,0.039896782407344414,0.10450955570257943,0.00984409835040549,0.018413460361851576,0.002126183875965392,0.023506279511915133,-0.011763287922302218,0.0005075793642077015,0.0077204595837774195,-0.019793503921768017,0.02940829111873333,-0.014293231850827178,0.04318965489751306,-0.0480774254377546,0.04136698467030736,0.023411763542941933,-0.042039787862449884,0.00947594205329018,-0.0030860043994395923,0.015506735373617568,0.04399403737022959,0.08289867588158312,0.022333357125873962,-0.028244875925432508,0.016429133380056707,0.054443227384110976,-0.0515108017957416,0.06778584979474545,0.0006057115036849715,-0.056708767656879176,0.0628362305719277,0.009779272498894112,-0.0023545143104174433,-0.04800801101172793,-0.07734973902075454,-0.03602449028604214,0.03567800254978496,0.034197270805979604,-0.040816437774177254,0.008703518651102589,0.022028252075336964,-0.0415938606742641,0.03972635940038439,0.09635748521521174,0.014070984395371413,0.01227214452328867,-0.09475001358780367,0.021235109195474465,-0.021782820000602252,0.02649204359502243,0.06437021641638772,-0.004583319226592981,-0.01986938435785023,-0.027010519440879982,0.04455232912481859,0.0607588745910546,-0.08578989256558747,0.03188484232744266,-0.04654071913582498,-0.05058052544963771,0.1462401501063643,-0.08104207790617284,0.05242066602383194,0.09758897562479152,0.003667611777300722,0.04532572427957223,0.07893792321455889,0.007804954623711166,0.03246927796060155,-0.07110405488517776,0.005019943377699551,-0.07687626046867206,-0.047155525214199356,0.0022281700600207577,-0.024901406975976863,-0.08840684265155216,0.03778957309008672,0.011140980494834871,-0.006989547314427408,-0.01945731383226491,-0.03411471541441077,0.048739581593665586,-0.13881510329143754,0.04037931795906404,0.1141204787739392,-0.05266589552549453,-0.08436076953236399,0.021568092581783906,-0.022252840227306947,-0.029199876075867437,0.06508748509503644,0.037151341021446314,0.004042465094494998,0.01020428093156154,0.04349330724377571,-0.014137525687491978,0.008101273129858748,0.015928811918550716,-0.04418383331584005,-0.08103222849554029,-0.0382715406795514,-0.0014375236707314001,-0.05384260881692171,0.04291804549123707,0.02046805208725534,-0.0013900216595331906,-0.06865624980679874,0.007758140760164805,0.04401981210785693,0.0256849607163719,0.021481808969461967,0.008827832839572156,0.11440639236363873,-0.006436499979513585,0.007964550096497484,-0.07074560668191006,-0.06429555707065196,-0.017979423557147222,0.036029792326534624,-0.023239507301758718,-0.03573990860504323,0.06005970966713182,0.028023924782936423,0.019336117786788863,0.01983697007807646,0.003765739767851332,-0.030881868926246232,0.07132344892055824,-0.02955966525367895,-0.017133256926799414,-0.04592337719453819,0.029483074707717733,-0.09826675031719537,0.013001378500999196,-0.05294574504910871,0.004635196110531731,0.04963825742617763,0.017034980075550273,0.037806761210206256,0.04232036152148041,0.012094870999950713,0.005204215365289389,-0.019584790077401677,0.03185024219243948,-0.011107684686631447,0.020483255707498253,0.057494086245524476,-0.06704135663036642,-0.033480213617841745,0.07719388475705838,-0.0062528905307709486,0.0006969927103611957,-0.01522777279601071,-0.017358632267508976,-0.019484200343240755,-0.057102405048649885,-0.03501504728949934,0.07019221545036496,0.07572564110159874,-0.024650863086772636,-0.0875906837654525,-0.01985601199226823,0.07298104664118125,0.037413348427748884,0.0011616072775911422,0.09168200387523093,0.008952356823007492,0.04636509905986745,0.039468552716525974,-0.019885230708088536,-0.028423968955456954,-0.01951354887418786,-0.02601983638255504,-0.005254610456678825,-0.030798536428282487,-0.03558343456223093,-0.05118288035536635,0.010503973158534038,-0.04067756450767147,-0.031071714342346995,0.024844086676803902,-0.018541790460685978,0.012702065153179913,0.04500884077800759,-0.07751070939261338,-0.044065682490452604,-0.016021165553583756,0.013731671865539752,-0.003769310128549912,0.05342676130862072,-0.002239083660242613,-0.05029611360153247,-0.05392139119192444,0.038098281112917014,0.024988388036506187,0.002969041892607369,0.018417823776715143,-0.056067326748422505,0.018319390378470916,0.012477484189479714,-0.05982122306936774,0.023933992456195166,-0.03407038854242399,-0.06582458114958015,-0.0021704752221482788,-0.02247413349185332,-0.05015290952448188,-0.01263468959900663,-0.0097404211937201,0.07768376068822269,0.03211997561397609,-0.01810258243168736,0.02246928176690086,-0.08787336264704836,-0.03952167114114453,-0.008428809718240922,-0.0351996633770137,-0.006409297949521091,0.05705444000918291,-0.06592274682018263,-0.05209530979908746,0.04655744082390748,-0.0035241836477984314,0.0011544361202360364,0.04716583800598465,0.02023317171802648,-0.006477349283519793,0.02618343754398541,0.03356296106056984,0.032218376929261563,0.0023530563791202145,-0.0006311093998976622,-0.005960396578553501,-0.07214969717736902,0.0007085758478406832,0.03547185439423754,-0.015053624147318758,0.03343241218605946,0.0033105846021749914,0.051412301555532836,0.006784216334726173,0.0025287374583685632,-0.033035582164302475,-0.038403945364828766,-0.019868204212704358,-0.04907445853640293,-0.03050950593475638,-0.01666445615259802,-0.0014492251289554808,0.042815139902562936,0.0495132369727924,-0.028810246854595,0.07967374460964367,0.022885093826736355,0.053263594267954094,-0.006237034474906981,0.05050630633044859,0.027708918562737002,-0.016718161078611526,-0.01643435411950059,-0.05347275952326841,0.0381264361263863,0.004416858503426388,0.03891825105930711,0.035645528150529696,0.014044698269572109,-0.008845668097223851,0.05951393087362421,0.028155180874505446,-0.01180434488171535,-0.045943127431232356,-0.07590700326294735,0.016165692895120973,0.04329341438052984,0.0046882159226540885,0.03208396220900889,-0.018347399431714338,-0.0170413568751679,-0.0006521148678012663,-0.11865089024449217",
                "vocoder": "n/a",
                "modelType": "xVAPitch",
                "instance_index": 0,
                "pace": 1.0
            }
            
            # Send synthesis request
            try:
                response = requests.post(
                    f"{self.server_url}/synthesize", 
                    json=payload, 
                    timeout=60
                )
            except Exception as e:
                # Server may crash due to xVAsynth bug but still write file before crashing
                pass
            
            # Wait for file generation (file may be written despite server error)
            time.sleep(2)
            
            # Check if file was created with .wav extension
            expected_file = Path(output_filename)
            
            if expected_file.exists():
                self.last_synthesis_file = str(expected_file)
                
                # Play audio if requested
                if play_audio:
                    self.play_audio(str(expected_file))
                
                return str(expected_file)
            else:
                self.log(f"Audio file not generated: {output_filename}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"Voice synthesis failed: {e}", "ERROR")
            return None
    
    def play_audio(self, file_path):
        """Play audio file using pygame"""
        try:
            if not Path(file_path).exists():
                self.log(f"Audio file not found: {file_path}", "ERROR")
                return False

            # Load and play audio
            self.is_playing = True
            self.playback_start_time = time.time()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()

            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            self.is_playing = False
            self.playback_start_time = None
            return True

        except Exception as e:
            self.is_playing = False
            self.playback_start_time = None
            self.log(f"Audio playback failed: {e}", "ERROR")
            return False
    
    def synthesize_async(self, text, play_audio=True):
        """Synthesize voice asynchronously"""
        def synthesize():
            self.synthesize_voice(text, play_audio)
        
        thread = threading.Thread(target=synthesize, daemon=True)
        thread.start()
        return thread
    
    def get_status(self):
        """Get comprehensive voice system status"""
        return {
            "initialized": self.is_initialized,
            "server_running": self.server_running and self.check_server_status(),
            "model_loaded": self.model_loaded,
            "server_url": self.server_url,
            "model_info": {
                "name": self.model_info.get('games', [{}])[0].get('voiceName', 'Unknown') if self.model_info else None,
                "type": self.model_info.get('modelType') if self.model_info else None,
                "author": self.model_info.get('author') if self.model_info else None
            },
            "last_synthesis": self.last_synthesis_file,
            "audio_output_dir": str(self.audio_output_dir),
            "is_playing": self.is_playing,
            "playback_duration": time.time() - self.playback_start_time if self.playback_start_time else 0
        }
    
    def cleanup_old_files(self, keep_last=10):
        """Clean up old audio files, keeping only the most recent ones"""
        try:
            audio_files = list(self.audio_output_dir.glob("*.wav"))
            audio_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove older files
            for file_path in audio_files[keep_last:]:
                try:
                    file_path.unlink()
                    self.log(f"Cleaned up old audio file: {file_path}")
                except Exception as e:
                    self.log(f"Failed to remove {file_path}: {e}", "WARN")
                    
        except Exception as e:
            self.log(f"Cleanup failed: {e}", "ERROR")
    
    def shutdown(self):
        """Complete system shutdown"""
        self.log("Shutting down voice system...")
        
        try:
            # Stop audio playback
            pygame.mixer.music.stop()
            
            # Stop server
            self.stop_server()
            
            # Clean up old files
            self.cleanup_old_files(5)
            
            self.log("Voice system shutdown complete")
            
        except Exception as e:
            self.log(f"Shutdown error: {e}", "ERROR")


# Example usage and testing
if __name__ == "__main__":
    # Initialize voice manager
    voice_manager = VoiceManager()
    
    try:
        # Initialize complete system
        result = voice_manager.initialize_complete_system()
        
        if result["success"]:
            print("\n" + "="*60)
            print("VOICE SYSTEM READY - Testing synthesis...")
            print("="*60)
            
            # Test voice synthesis
            test_text = "Assaultron unit ASR-7 online. Voice systems operational. Standing by for orders."
            audio_file = voice_manager.synthesize_voice(test_text)
            
            if audio_file:
                print(f"\nVoice test successful! Audio saved to: {audio_file}")
                
                # Show status
                status = voice_manager.get_status()
                print(f"\nSystem Status: {json.dumps(status, indent=2)}")
            else:
                print("\nVoice test failed!")
        else:
            print(f"\nFailed to initialize voice system: {result['error']}")
    
    finally:
        # Shutdown
        print("\nShutting down...")
        voice_manager.shutdown()