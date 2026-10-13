//! A scripted HTTP server for the license client tests: each `METHOD /path` answers with a
//! fixed status and JSON body, and every request is recorded.

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpListener;
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone)]
pub struct Recorded {
    pub path: String,
    /// Header names lower-cased.
    pub headers: Vec<(String, String)>,
    pub body: serde_json::Value,
}

impl Recorded {
    pub fn header(&self, name: &str) -> Option<String> {
        self.headers
            .iter()
            .find(|(key, _)| key == name)
            .map(|(_, value)| value.clone())
    }
}

#[derive(Default)]
struct State {
    routes: HashMap<String, (u16, String)>,
    requests: Vec<Recorded>,
}

pub struct ScriptedServer {
    pub base: String,
    state: Arc<Mutex<State>>,
}

impl ScriptedServer {
    pub fn start() -> ScriptedServer {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let base = format!("http://{}", listener.local_addr().unwrap());
        let state = Arc::new(Mutex::new(State::default()));
        let thread_state = state.clone();
        std::thread::spawn(move || {
            for stream in listener.incoming().flatten() {
                let _ = serve(stream, &thread_state);
            }
        });
        ScriptedServer { base, state }
    }

    pub fn route(&self, method: &str, path: &str, status: u16, body: serde_json::Value) {
        self.state
            .lock()
            .unwrap()
            .routes
            .insert(format!("{method} {path}"), (status, body.to_string()));
    }

    pub fn requests(&self) -> Vec<Recorded> {
        self.state.lock().unwrap().requests.clone()
    }
}

fn serve(stream: std::net::TcpStream, state: &Mutex<State>) -> std::io::Result<()> {
    let mut reader = BufReader::new(stream.try_clone()?);
    let mut line = String::new();
    reader.read_line(&mut line)?;
    let mut parts = line.split_whitespace();
    let method = parts.next().unwrap_or_default().to_owned();
    let path = parts.next().unwrap_or_default().to_owned();
    let mut length = 0usize;
    let mut headers = Vec::new();
    loop {
        let mut header = String::new();
        if reader.read_line(&mut header)? == 0 || header == "\r\n" {
            break;
        }
        if let Some((name, value)) = header.split_once(':') {
            let (name, value) = (name.trim().to_ascii_lowercase(), value.trim().to_owned());
            if name == "content-length" {
                length = value.parse().unwrap_or(0);
            }
            headers.push((name, value));
        }
    }
    let mut body = vec![0; length];
    reader.read_exact(&mut body)?;

    let (status, response) = {
        let mut state = state.lock().unwrap();
        state.requests.push(Recorded {
            path: path.clone(),
            headers,
            body: serde_json::from_slice(&body).unwrap_or(serde_json::Value::Null),
        });
        state
            .routes
            .get(&format!("{method} {path}"))
            .cloned()
            .unwrap_or((404, r#"{"error":"not_found"}"#.to_owned()))
    };
    let mut stream = stream;
    write!(
        stream,
        "HTTP/1.1 {status} X\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{response}",
        response.len()
    )?;
    stream.flush()
}
