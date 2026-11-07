"""Single-owner video downloader. Deploy one process/replica behind HTTPS."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import hmac
import os
from pathlib import Path
import secrets
import shutil
import threading
import time
from urllib.parse import urlparse

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
import yt_dlp

BASE = Path(__file__).resolve().parent
SESSION_AGE = 12 * 3600
LIMIT = 3 * 1024**3

def valid_url(url):
    p = urlparse(url)
    return (p.scheme == 'https' and not p.username and not p.password and
            p.port in (None, 443) and (p.hostname or '').lower() in {
                'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'})

def create_app(*, password=None, secret=None, storage=None, secure=True, downloader=None):
    password = password or os.environ.get('APP_PASSWORD', '')
    secret = secret or os.environ.get('SESSION_SECRET', '')
    if len(password) < 16 or len(secret) < 32:
        raise RuntimeError('Configura APP_PASSWORD (mínim 16 caràcters) i SESSION_SECRET (mínim 32).')
    store = Path(storage or os.environ.get('DOWNLOAD_DIR', '/tmp/video-downloader')).resolve()
    store.mkdir(parents=True, exist_ok=True)
    signer = URLSafeTimedSerializer(secret, salt='video-owner-v1')
    lock = threading.RLock()
    sessions, failures, jobs = {}, {}, {}
    pool = ThreadPoolExecutor(max_workers=1)

    def token_data(request):
        try:
            data = signer.loads(request.cookies.get('video_session', ''), max_age=SESSION_AGE)
            with lock:
                if data['sid'] in sessions:
                    return data
        except (BadSignature, SignatureExpired, KeyError, TypeError):
            pass
        return None

    def public_job(job):
        return {k: job[k] for k in ('id', 'state', 'progress', 'message', 'filename')}

    def purge_finished():
        now = time.time()
        with lock:
            finished = sorted((j for j in jobs.values() if j['state'] in ('ready', 'error') and not j['readers']), key=lambda j: j['finished'])
            for i, job in enumerate(finished):
                if now - job['finished'] > 3600 or len(finished) - i >= 3:
                    shutil.rmtree(store / job['id'], ignore_errors=True)
                    jobs.pop(job['id'], None)

    def run_download(job, url, height):
        folder = store / job['id']
        folder.mkdir()
        def progress(data):
            used = sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
            if used > LIMIT or shutil.disk_usage(store).free < 256 * 1024**2:
                raise RuntimeError('No hi ha prou espai temporal per completar aquest vídeo.')
            with lock:
                if data.get('status') == 'downloading':
                    total = data.get('total_bytes') or data.get('total_bytes_estimate')
                    job['progress'] = min(99, int(100 * data.get('downloaded_bytes', 0) / total)) if total else 0
                    job['message'] = 'Descarregant vídeo i àudio…'
                elif data.get('status') == 'finished':
                    job['message'] = 'Preparant el fitxer MP4…'
        try:
            with lock:
                job.update(state='downloading', message='Connectant amb YouTube…')
            opts = {
                'format': f'bv[height<={height}][ext=mp4][vcodec^=avc1]+ba[ext=m4a]/b[height<={height}][ext=mp4]/bv[height<={height}][ext=mp4]+ba[ext=m4a]',
                'merge_output_format': 'mp4', 'noplaylist': True,
                'outtmpl': str(folder / '%(title).120s [%(id)s].%(ext)s'),
                'windowsfilenames': True, 'cachedir': False,
                'js_runtimes': {'deno': {}}, 'quiet': True, 'no_warnings': True,
                'socket_timeout': 30, 'retries': 2, 'extractor_retries': 2,
                'max_filesize': LIMIT, 'match_filter': lambda info, *, incomplete: (
                    'No es descarreguen emissions en directe ni vídeos de més de quatre hores.'
                    if info.get('is_live') or (info.get('duration') or 0) > 14400 else None),
                'progress_hooks': [progress],
            }
            if downloader:
                result = Path(downloader(url, height, folder, progress)).resolve()
            else:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    result = Path(ydl.prepare_filename(info)).with_suffix('.mp4').resolve()
            if result.parent != folder.resolve() or not result.is_file() or result.suffix.lower() != '.mp4':
                raise RuntimeError('No s’ha pogut crear el fitxer MP4.')
            if result.stat().st_size > LIMIT:
                raise RuntimeError('El vídeo supera el límit de 3 GB.')
            with lock:
                job.update(state='ready', progress=100, message='Vídeo preparat. Ja el pots guardar al teu dispositiu.', filename=result.name, path=result, finished=time.time())
        except Exception:
            # Provider errors can include signed URLs; never expose them to visitors or logs.
            with lock:
                job.update(state='error', message='No s’ha pogut descarregar. Revisa l’enllaç, la disponibilitat del vídeo o l’espai temporal. YouTube pot restringir les connexions des d’aquest servidor.', finished=time.time())
            shutil.rmtree(folder, ignore_errors=True)

    async def home(request):
        return FileResponse(BASE / 'static' / ('index.html' if request.state.identity else 'login.html'), media_type='text/html')

    async def login(request):
        ip = request.client.host if request.client else 'unknown'
        now = time.time()
        with lock:
            for key in list(failures):
                if now - failures[key][0] > 300:
                    failures.pop(key)
            if len(failures) > 1000 or failures.get(ip, (0, 0))[1] >= 5:
                return JSONResponse({'error': 'Massa intents. Espera cinc minuts.'}, status_code=429)
        try:
            data = await request.json()
            entered = data.get('password', '')
            if not isinstance(entered, str) or len(entered) > 1024:
                raise ValueError()
        except (ValueError, AttributeError):
            return JSONResponse({'error': 'Dades no vàlides.'}, status_code=400)
        if not hmac.compare_digest(entered.encode(), password.encode()):
            with lock:
                start, count = failures.get(ip, (now, 0))
                failures[ip] = (start, count + 1)
            return JSONResponse({'error': 'Contrasenya incorrecta.'}, status_code=401)
        sid = secrets.token_urlsafe(32)
        with lock:
            failures.pop(ip, None)
            for key in list(sessions):
                if now - sessions[key] > SESSION_AGE:
                    sessions.pop(key)
            if len(sessions) >= 32:
                sessions.pop(next(iter(sessions)))
            sessions[sid] = now
        response = JSONResponse({'ok': True})
        response.set_cookie('video_session', signer.dumps({'sid': sid, 'csrf': secrets.token_urlsafe(32)}), max_age=SESSION_AGE, httponly=True, secure=secure, samesite='strict')
        return response

    async def session_info(request):
        purge_finished()
        with lock:
            return JSONResponse({'csrf': request.state.identity['csrf'], 'jobs': [public_job(j) for j in jobs.values()]})

    async def logout(request):
        with lock:
            sessions.pop(request.state.identity['sid'], None)
        response = JSONResponse({'ok': True})
        response.delete_cookie('video_session', secure=secure, httponly=True, samesite='strict')
        return response

    async def start(request):
        try:
            data = await request.json()
            url, height = data.get('url', ''), data.get('height', 720)
            if not isinstance(url, str) or not valid_url(url) or height not in (480, 720, 1080):
                raise ValueError()
        except (ValueError, AttributeError):
            return JSONResponse({'error': 'Introdueix un enllaç HTTPS de YouTube i una qualitat vàlida.'}, status_code=400)
        purge_finished()
        with lock:
            if any(j['state'] in ('queued', 'downloading') for j in jobs.values()):
                return JSONResponse({'error': 'Espera que acabi la descàrrega actual.'}, status_code=409)
            if shutil.disk_usage(store).free < 512 * 1024**2:
                return JSONResponse({'error': 'No hi ha prou espai temporal al servidor.'}, status_code=507)
            job = {'id': secrets.token_hex(16), 'created': time.time(), 'state': 'queued', 'progress': 0,
                   'message': 'Preparant la descàrrega…', 'filename': None, 'path': None, 'readers': 0}
            jobs[job['id']] = job
            pool.submit(run_download, job, url, height)
            return JSONResponse(public_job(job), status_code=202)

    async def status(request):
        with lock:
            job = jobs.get(request.path_params['job_id'])
            return JSONResponse(public_job(job)) if job else JSONResponse({'error': 'El fitxer ha caducat o ja no existeix.'}, status_code=404)

    async def download(request):
        with lock:
            job = jobs.get(request.path_params['job_id'])
            if not job or job['state'] != 'ready' or not job['path'].is_file():
                return JSONResponse({'error': 'El fitxer no està disponible.'}, status_code=404)
            job['readers'] += 1
        def done():
            with lock:
                job['readers'] -= 1
        return FileResponse(job['path'], media_type='video/mp4', filename=job['filename'], background=BackgroundTask(done))

    async def health(request):
        return Response('ok', media_type='text/plain')

    @asynccontextmanager
    async def lifespan(app):
        async def cleanup():
            while True:
                await asyncio.sleep(60)
                purge_finished()
        task = asyncio.create_task(cleanup())
        yield
        task.cancel()
        pool.shutdown(wait=False, cancel_futures=True)

    class Gate(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.identity = token_data(request)
            if request.method == 'POST':
                if request.headers.get('origin', '').rstrip('/') != str(request.base_url).rstrip('/'):
                    return JSONResponse({'error': 'Origen no autoritzat.'}, status_code=403)
                try:
                    length = int(request.headers.get('content-length', '0') or '0')
                except ValueError:
                    return JSONResponse({'error': 'Petició no vàlida.'}, status_code=400)
                if length > 4096:
                    return JSONResponse({'error': 'Petició massa gran.'}, status_code=413)
            if request.url.path.startswith('/api/') and request.url.path != '/api/login':
                if not request.state.identity:
                    return JSONResponse({'error': 'Torna a iniciar sessió.'}, status_code=401)
                if request.method == 'POST' and not hmac.compare_digest(request.headers.get('x-csrf-token', ''), request.state.identity['csrf']):
                    return JSONResponse({'error': 'Sessió no vàlida. Recarrega la pàgina.'}, status_code=403)
            response = await call_next(request)
            response.headers.update({
                'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
                'X-Robots-Tag': 'noindex, nofollow',
                'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            })
            return response

    app = Starlette(routes=[Route('/', home), Route('/health', health),
        Route('/api/login', login, methods=['POST']), Route('/api/session', session_info),
        Route('/api/logout', logout, methods=['POST']), Route('/api/jobs', start, methods=['POST']),
        Route('/api/jobs/{job_id}', status), Route('/api/jobs/{job_id}/download', download),
        Mount('/static', app=StaticFiles(directory=BASE / 'static'))], lifespan=lifespan)
    app.add_middleware(Gate)
    return app
