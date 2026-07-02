const { app, BrowserWindow, shell, Menu } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const kill = require('tree-kill');

let win = null;
let serverProcess = null;
const SERVER_URL = 'http://localhost:8000';

function startServer() {
  const python     = '/opt/miniconda3/bin/python3';
  const serverPath = '/Users/conradgarnett/bloomberg/server.py';
  const serverCwd  = '/Users/conradgarnett/bloomberg';
  serverProcess = spawn(python, ['-u', serverPath], {
    cwd: serverCwd,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  serverProcess.stdout.on('data', d => console.log('[server]', d.toString().trim()));
  serverProcess.stderr.on('data', d => console.error('[server]', d.toString().trim()));
  serverProcess.on('exit', code => console.log('[server] exited', code));
}

function isServerRunning(cb) {
  const req = http.get('http://localhost:8000/api/status', res => {
    res.resume(); cb(res.statusCode < 500);
  });
  req.on('error', () => cb(false));
  req.setTimeout(1000, () => { req.destroy(); cb(false); });
}

function waitForServer(cb, attempts = 0) {
  if (attempts > 80) { cb(new Error('timeout')); return; }
  const req = http.get(SERVER_URL, res => {
    res.resume();
    if (res.statusCode < 500) cb(null);
    else setTimeout(() => waitForServer(cb, attempts + 1), 500);
  });
  req.on('error', () => setTimeout(() => waitForServer(cb, attempts + 1), 500));
  req.setTimeout(1000, () => { req.destroy(); setTimeout(() => waitForServer(cb, attempts + 1), 500); });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1600, height: 1000, minWidth: 1100, minHeight: 700,
    title: 'Delta Terminal',
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#f5f1e6',
    show: false,
    webPreferences: { nodeIntegration: false, contextIsolation: true, webSecurity: false },
  });

  win.loadURL('data:text/html,<html style="background:%23f5f1e6;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh;margin:0"><div style="text-align:center"><div style="font-size:56px;color:%238a3a0c">◆</div><div style="font-size:13px;letter-spacing:.22em;margin-top:14px;color:%231a1208">DELTA TERMINAL</div><div style="font-size:10px;color:%236a5d40;margin-top:10px;letter-spacing:.1em">LOADING...</div></div></html>');

  win.once('ready-to-show', () => win.show());

  isServerRunning(already => {
    if (already) {
      win.loadURL(SERVER_URL);
    } else {
      startServer();
      waitForServer(err => {
        if (!win) return;
        if (err) {
          win.loadURL('data:text/html,<body style="font-family:monospace;padding:40px;background:%23f5f1e6"><h2 style="color:%23c81d1d">Backend failed to start</h2><p>Try running python3 ~/bloomberg/server.py in Terminal.</p></body>');
          return;
        }
        win.loadURL(SERVER_URL);
      });
    }
  });

  win.on('closed', () => { win = null; });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith('http://localhost')) shell.openExternal(url);
    return { action: 'deny' };
  });
}

function buildMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Delta Terminal', submenu: [
      { label: 'Reload', accelerator: 'CmdOrCtrl+R', click: () => win?.loadURL(SERVER_URL) },
      { label: 'DevTools', accelerator: 'CmdOrCtrl+Option+I', click: () => win?.webContents.toggleDevTools() },
      { type: 'separator' },
      { label: 'Zoom In',    accelerator: 'CmdOrCtrl+=', click: () => win?.webContents.setZoomLevel(win.webContents.getZoomLevel() + 0.5) },
      { label: 'Zoom Out',   accelerator: 'CmdOrCtrl+-', click: () => win?.webContents.setZoomLevel(win.webContents.getZoomLevel() - 0.5) },
      { label: 'Reset Zoom', accelerator: 'CmdOrCtrl+0', click: () => win?.webContents.setZoomLevel(0) },
      { type: 'separator' },
      { role: 'quit' },
    ]},
    { label: 'Edit', submenu: [{ role: 'undo' },{ role: 'redo' },{ type: 'separator' },{ role: 'cut' },{ role: 'copy' },{ role: 'paste' },{ role: 'selectAll' }] },
    { label: 'Window', submenu: [{ role: 'minimize' },{ role: 'zoom' },{ label: 'Full Screen', accelerator: 'Ctrl+Cmd+F', click: () => win?.setFullScreen(!win.isFullScreen()) }] },
  ]));
}

app.whenReady().then(() => {
  buildMenu();
  createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', () => { if (serverProcess?.pid) kill(serverProcess.pid, 'SIGTERM'); });
