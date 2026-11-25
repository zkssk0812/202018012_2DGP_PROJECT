"""테스트용 릴리즈(Windows 실행 파일) 만들기.

    python tools/build_release.py [버전]          예) python tools/build_release.py 0.3

결과 (release/ 폴더는 git 에서 제외되어 있음):
    release/텅빈정령_v<버전>/EmptySpirit.exe   더블클릭으로 실행 (파이썬 설치 필요 없음)
    release/텅빈정령_v<버전>/Resource/          게임 그림 · 맵 (zip · 그림 생성 스크립트는 빼고)
    release/텅빈정령_v<버전>/읽어주세요.txt       조작법 · 오류 보고 방법
    release/텅빈정령_v<버전>.zip               위 폴더를 그대로 압축 (지인에게 보낼 파일)

PyInstaller 가 필요하다. 설치되어 있지 않으면  pip install pyinstaller
(다른 폴더에 설치했다면 PYINSTALLER_PATH 환경 변수로 그 폴더를 알려 준다.)
"""
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, 'game')
RELEASE = os.path.join(ROOT, 'release')
EXE_NAME = 'EmptySpirit'
SKIP_EXT = ('.zip', '.py', '.pyc')

README = """텅 빈 정령 — 테스트판 v{version}

■ 실행
  EmptySpirit.exe 를 더블클릭하세요. (Resource 폴더는 exe 옆에 그대로 두어야 합니다)
  Windows 보안 경고가 뜨면 [추가 정보] → [실행] 을 눌러 주세요.

■ 조작
  방향키      이동
  Space       회피 (잠깐 무적)
  Q W E R     기술
  F           쓰러진 정령의 검은 기운 흡수 (가까이에서)
  ←→ / Enter  기술 배우기 창에서 고르기 · 정하기 (Esc 뒤로)
  J           이야기 연출 건너뛰기
  P           튜토리얼 전체 건너뛰기 (튜토리얼 중에만)
  Esc         게임 종료

■ 진행
  튜토리얼 숲 → 북쪽 길 → 숲1 (수풀에서 정령 조우, 끝의 길목에 실프)
  → 숲2 (끝의 길목에 노움) → (숲3 은 아직 준비 중)

■ 테스트용 관리자 키 (T 로 켜고 끔)
  1  실프 앞으로 (Lv10)        2  노움 앞으로 (Lv18)
  I  무적 켜기/끄기            G  전투 중 상대 바로 쓰러뜨리기
  K  기술 선택 창              U  맞는 범위 보기

■ 오류가 나면
  게임이 갑자기 꺼지면 exe 옆에 error_log.txt 가 생깁니다. 이 파일을 보내 주세요.
  어디서 무엇을 하다가 생겼는지 한 줄 적어 주시면 큰 도움이 됩니다!
"""


def copy_resources(dst):
    src = os.path.join(ROOT, 'Resource')
    for folder, _, files in os.walk(src):
        rel = os.path.relpath(folder, src)
        if '__pycache__' in rel:
            continue
        for name in files:
            if name.lower().endswith(SKIP_EXT):
                continue
            out = os.path.join(dst, rel, name)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copy2(os.path.join(folder, name), out)


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else '0.1'
    name = f'텅빈정령_v{version}'
    out_dir = os.path.join(RELEASE, name)
    work = os.path.join(RELEASE, '_build')
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    env = dict(os.environ)
    if env.get('PYINSTALLER_PATH'):
        env['PYTHONPATH'] = env['PYINSTALLER_PATH'] + os.pathsep + env.get('PYTHONPATH', '')
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
           '--name', EXE_NAME, '--distpath', os.path.join(work, 'dist'), '--workpath', os.path.join(work, 'work'),
           '--specpath', work, '--paths', GAME,
           '--collect-all', 'sdl2dll',               # SDL2 · 이미지 · 글꼴 · 소리 DLL
           '--collect-submodules', 'sdl2',
           '--collect-all', 'pico2d',
           '--collect-submodules', 'transitions',
           os.path.join(GAME, 'main.py')]
    print('PyInstaller 실행 중...')
    subprocess.run(cmd, check=True, env=env, cwd=ROOT)

    shutil.move(os.path.join(work, 'dist', EXE_NAME), out_dir)
    print('Resource 복사 중...')
    copy_resources(os.path.join(out_dir, 'Resource'))
    with open(os.path.join(out_dir, '읽어주세요.txt'), 'w', encoding='utf-8-sig') as f:
        f.write(README.format(version=version))
    shutil.rmtree(work, ignore_errors=True)

    zip_path = os.path.join(RELEASE, f'{name}.zip')
    print('압축 중...')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(out_dir):
            for fn in files:
                full = os.path.join(folder, fn)
                z.write(full, os.path.join(name, os.path.relpath(full, out_dir)))
    size = os.path.getsize(zip_path) / 1024 / 1024
    print(f'완료: {zip_path} ({size:.1f} MB)')


if __name__ == '__main__':
    main()
