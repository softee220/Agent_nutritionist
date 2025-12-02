import os
import pkgutil
import pkg_resources
import ast

PROJECT_DIR = "."  # 현재 폴더 기준


def extract_imports_from_file(filepath):
    """Python 파일에서 import된 모듈 이름을 추출"""
    imports = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            node = ast.parse(f.read(), filename=filepath)
        for n in ast.walk(node):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom):
                if n.module is not None:
                    imports.add(n.module.split(".")[0])
    except Exception as e:
        print(f"[WARN] {filepath} 파싱 중 오류 발생: {e}")
    return imports


def get_all_imports(project_root):
    """프로젝트 전체 .py 파일에서 import된 모듈 수집"""
    imported_modules = set()
    for root, _, files in os.walk(project_root):
        for f in files:
            if f.endswith(".py"):
                filepath = os.path.join(root, f)
                modules = extract_imports_from_file(filepath)
                imported_modules.update(modules)
    return imported_modules


def map_modules_to_packages(imports):
    """import된 모듈 중 pip 패키지에 해당하는 것만 찾아 반환"""
    installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
    found_requirements = {}

    for module in imports:
        for pkg in installed_packages:
            try:
                dist = pkg_resources.get_distribution(pkg)
                top_level_names = dist._get_metadata("top_level.txt")
                if module in top_level_names:
                    found_requirements[pkg] = installed_packages[pkg]
            except Exception:
                pass

    return found_requirements


def write_requirements(requirements):
    with open("requirements.txt", "w", encoding="utf-8") as f:
        for pkg, ver in sorted(requirements.items()):
            f.write(f"{pkg}=={ver}\n")
    print("requirements.txt 생성 완료!")


if __name__ == "__main__":
    print("📌 프로젝트 import 스캔 중...")
    imports = get_all_imports(PROJECT_DIR)

    print(f"📌 감지된 import 모듈: {imports}")

    print("📌 pip 패키지와 매핑 중...")
    requirements = map_modules_to_packages(imports)

    write_requirements(requirements)
