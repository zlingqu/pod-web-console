
console.log(window,document.documentElement, $(window).height(), $(window).width())

let term,
    websocket,
    search_obj = {}
    containerTerm = document.getElementById('#terminal')

window.location.search.replace('?','').split('&').forEach(
    item => {
        search_obj[item.split('=')[0]] = item.split('=')[1]
    });

document.getElementById('terminal').style.height = window.innerHeight + 'px';
document.getElementById('terminal').style.width = window.innerWidth + 'px';
createTerminal()



function initWebsocket(){
    let ws_url = 'ws://' + `${window.location.host}` + '/terminal/' +
    search_obj['region'] + '/' +
    search_obj['namespace'] + '/' +
    search_obj['pod'] + '/' +
    search_obj['container'] + '?' +
    'cols=' + term.cols + '&' +
    'rows=' + term.rows;
    websocket = new WebSocket(ws_url);
}

function createTerminal() {
    
    term = new Terminal({
        cursorBlink: true
    });

    term.open(containerTerm, false);
    // console.log(term.cols, term.rows);
    term.fit(); // 根据屏幕大小自动调整term.cols, term.rows
    initWebsocket() // term.cols, term.rows 通过websocket请求传到后端
    // console.log(term.cols, term.rows);
    
    websocket.onopen = runRealTerminal;
    websocket.onclose = runFakeTerminal;
    websocket.onerror = runFakeTerminal;
}

function runRealTerminal() {
    term.writeln("\x1b[33m欢迎使用 kubernetes web terminal!   \x1b[0m ");
    term.attach(websocket);

    term._initialized = true;
  }

  function runFakeTerminal() {
    term.writeln(" ");
    term.writeln("已退出. 感谢使用!");
  }