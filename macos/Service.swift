import AppKit
import Network
final class Service: NSObject, NSApplicationDelegate {
 let root = URL(fileURLWithPath: Bundle.main.object(forInfoDictionaryKey:"PilotRoot") as! String)
 var child: Process?
 var stopping = false
 var probe: NWConnection?
 func applicationDidFinishLaunching(_ note: Notification) {
  let c = NWConnection(host:NWEndpoint.Host(Bundle.main.object(forInfoDictionaryKey:"PicoHost") as! String),port:8766,using:.tcp);probe=c
  c.stateUpdateHandler = { state in
   let text=String(describing:state)
   try? text.write(to:self.root.appendingPathComponent("logs/app-network-probe.txt"),atomically:true,encoding:.utf8)
   if case .ready = state {
    c.cancel()
    if CommandLine.arguments.contains("--probe-only") { NSApp.terminate(nil); return }
    self.start()
   }
  }
  c.start(queue:.main)
 }
 func applicationWillTerminate(_ note: Notification) { stopping=true;child?.terminate();child?.waitUntilExit();probe?.cancel() }
 func start() {
  let p=Process();p.executableURL=root.appendingPathComponent(".venv/bin/python")
  p.arguments=[root.appendingPathComponent("supervisor.py").path]
  p.currentDirectoryURL=root
  let log=root.appendingPathComponent("logs/supervisor.log")
  if !FileManager.default.fileExists(atPath:log.path){FileManager.default.createFile(atPath:log.path,contents:nil)}
  let out=try! FileHandle(forWritingTo:log);try? out.seekToEnd();p.standardOutput=out;p.standardError=out
  p.terminationHandler={_ in DispatchQueue.main.asyncAfter(deadline:.now()+3){ if !self.stopping { self.start() } }}
  do{try p.run();child=p}catch{try? String(describing:error).write(to:root.appendingPathComponent("logs/app-start-error.txt"),atomically:true,encoding:.utf8)}
 }
}
let a=NSApplication.shared;let d=Service();a.delegate=d;a.setActivationPolicy(.accessory);a.run()
