//! A tiny HTTP/1.1 file server for the download tests: serves byte ranges, and can be
//! told to ignore `Range` or to drop the connection partway through a body.

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Behaviour {
    Normal,
    /// Answer every request with 200 and the whole body, as a server without range
    /// support does.
    IgnoreRange,
    /// Send the headers for the full response, then only this many body bytes, then
    /// close: an interrupted transfer.
    CutAfter(usize),
}

#[derive(Default)]
struct State {
    files: HashMap<String, Vec<u8>>,
    behaviour: HashMap<String, Behaviour>,
    ranges: Vec<Option<u64>>,
}

pub struct TestServer {
    pub base: String,
    state: Arc<Mutex<State>>,
    requests: Arc<AtomicUsize>,
}

impl TestServer {
    pub fn start() -> TestServer {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let base = format!("http://{}", listener.local_addr().unwrap());
        let state = Arc::new(Mutex::new(State::default()));
        let requests = Arc::new(AtomicUsize::new(0));
        let (thread_state, thread_requests) = (state.clone(), requests.clone());
        std::thread::spawn(move || {
            for stream in listener.incoming().flatten() {
                thread_requests.fetch_add(1, Ordering::SeqCst);
                let _ = serve(stream, &thread_state);
            }
        });
        TestServer {
            base,
            state,
            requests,
        }
    }

    pub fn put(&self, path: &str, body: Vec<u8>) {
        self.state
            .lock()
            .unwrap()
            .files
            .insert(path.to_owned(), body);
    }

    pub fn set_behaviour(&self, path: &str, behaviour: Behaviour) {
        self.state
            .lock()
            .unwrap()
            .behaviour
            .insert(path.to_owned(), behaviour);
    }

    pub fn url(&self, path: &str) -> String {
        format!("{}/{}", self.base, path.trim_start_matches('/'))
    }

    /// The `Range` start offset of every request so far, `None` for a request without one.
    pub fn ranges(&self) -> Vec<Option<u64>> {
        self.state.lock().unwrap().ranges.clone()
    }

    pub fn request_count(&self) -> usize {
        self.requests.load(Ordering::SeqCst)
    }
}

/// A tar.zst laid out like a real runtime pack: an executable `python/bin/python3`
/// (when `with_python`) and a library file.
pub fn runtime_archive(with_python: bool) -> Vec<u8> {
    runtime_archive_with(with_python.then_some(b"#!/bin/sh\n".as_slice()))
}

/// As [`runtime_archive`], with `python` as the interpreter's contents (a shell script
/// standing in for it).
pub fn runtime_archive_with(python: Option<&[u8]>) -> Vec<u8> {
    // python-build-standalone ships `.tar.gz`.
    let mut encoder = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::fast());
    {
        let mut tar = tar::Builder::new(&mut encoder);
        let mut add = |name: &str, body: &[u8], mode: u32| {
            let mut header = tar::Header::new_gnu();
            header.set_size(body.len() as u64);
            header.set_mode(mode);
            header.set_cksum();
            tar.append_data(&mut header, name, body).unwrap();
        };
        if let Some(python) = python {
            add("python/bin/python3", python, 0o755);
        }
        add("python/lib/site.py", b"", 0o644);
        tar.finish().unwrap();
    }
    encoder.finish().unwrap()
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    use sha2::Digest;
    sha2::Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

fn serve(stream: TcpStream, state: &Mutex<State>) -> std::io::Result<()> {
    let mut reader = BufReader::new(stream.try_clone()?);
    let mut request_line = String::new();
    reader.read_line(&mut request_line)?;
    let path = request_line
        .split_whitespace()
        .nth(1)
        .unwrap_or("/")
        .trim_start_matches('/')
        .to_owned();
    let mut range_start = None;
    loop {
        let mut line = String::new();
        if reader.read_line(&mut line)? == 0 || line == "\r\n" {
            break;
        }
        if let Some(value) = line.to_ascii_lowercase().strip_prefix("range: bytes=") {
            range_start = value.trim().trim_end_matches('-').parse::<u64>().ok();
        }
    }

    let (body, behaviour) = {
        let mut state = state.lock().unwrap();
        state.ranges.push(range_start);
        (
            state.files.get(&path).cloned(),
            state
                .behaviour
                .get(&path)
                .copied()
                .unwrap_or(Behaviour::Normal),
        )
    };
    let mut stream = stream;
    let Some(body) = body else {
        write!(
            stream,
            "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        )?;
        return Ok(());
    };

    let start = match (behaviour, range_start) {
        (Behaviour::IgnoreRange, _) | (_, None) => 0,
        (_, Some(start)) => start.min(body.len() as u64) as usize,
    };
    let slice = &body[start..];
    if start > 0 {
        write!(
            stream,
            "HTTP/1.1 206 Partial Content\r\nContent-Length: {}\r\nContent-Range: bytes {}-{}/{}\r\nConnection: close\r\n\r\n",
            slice.len(),
            start,
            body.len() - 1,
            body.len()
        )?;
    } else {
        write!(
            stream,
            "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
            slice.len()
        )?;
    }
    match behaviour {
        Behaviour::CutAfter(n) => stream.write_all(&slice[..n.min(slice.len())])?,
        _ => stream.write_all(slice)?,
    }
    stream.flush()
}
