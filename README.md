# flask_ollama_web


This Python module spanns a web server up that interacts with a AI system running locally and listening at http://localhost:11434/api/chat. There the questions will be asked.

# Install

You need a [local ollama installation](https://ollama.com/download/) and a 'running' ollama instance to connect to.

Once you have installed ollama you can download and start whichever model ollama supports.
E.g. start with a rather small model like llama3
```
ollama run llama3
```

With this you can install the flask ollama frontend like this:

```
pip install git+https://github.com/stela2502/flask_ollama_web.git
```

# Usage

```
echo "from flask_ollama_web.routes import app


if __name__ == \"__main__\":
    app.run(host=\"0.0.0.0\", port=8080)" > /app/run.py
```

And then simply

```
 /app/run.py
```

```
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8080
 * Running on http://<external IP>:8080
```

This will start a single flask server that you can connect to.
And interact in a very simplye way:

[A simple oolama web interface](path/to/SimpleInterface.png)]

One big benefit from this is that you can see the answer in html and copy it in markdown ;-)