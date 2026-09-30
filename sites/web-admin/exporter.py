#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

StarClub 静态网站导出器 v0.9

将动态数据导出为纯静态 HTML 文件

用法: python exporter.py

      python exporter.py --page index

      python exporter.py --output ./dist

"""



import os

import sys

import json

import shutil

from datetime import datetime



# 设置 UTF-8 编码

if sys.platform == 'win32':

    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')



from jinja2 import Environment, FileSystemLoader, select_autoescape

from typing import Dict, Any, Optional



# ==================== 配置 ====================



SITE_ROOT = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(SITE_ROOT, 'data', 'site-data.json')

TEMPLATE_DIR = os.path.join(SITE_ROOT, 'templates')

OUTPUT_DIR = os.path.join(os.path.dirname(SITE_ROOT), 'web')

STATIC_DIR = os.path.join(SITE_ROOT, 'static')

CSS_DIR = os.path.join(SITE_ROOT, 'css')

JS_DIR = os.path.join(SITE_ROOT, 'js')





# ==================== 工具函数 ====================



def escape_html(text: str) -> str:

    """HTML转义"""

    if not text:

        return ''

    return (text

        .replace('&', '&amp;')

        .replace('<', '&lt;')

        .replace('>', '&gt;')

        .replace('"', '&quot;')

        .replace("'", '&#39;'))





def nl2br(text: str) -> str:

    """换行符转<br>，同时在中文标号（一）（二）…前自动插入<br>"""

    import re

    if not text:

        return ''

    # 先按 \n 分割，逐行转义，再拼合

    lines = text.split('\n')

    escaped_lines = [escape_html(line) for line in lines]

    result = '<br>'.join(escaped_lines)

    # 在每个中文标号（一）（二）…前插入 <br>（行首的标号除外）

    result = re.sub(r'(?<!<br>)（[一二三四五六七八九十]+）', r'<br>\g<0>', result)

    # 去掉开头可能多出的 <br>

    if result.startswith('<br>（'):

        result = result[4:]

    return result





def fix_uploads_path(path: str) -> str:

    """修复内链图片路径：/uploads/ -> uploads/ (相对路径)"""

    if path and path.startswith('/uploads/'):

        return 'uploads/' + path[9:]  # 去掉前导 /uploads/，加上相对路径前缀

    return path



def fix_uploads_path_for_pages(path: str) -> str:

    """修复详情页中的内链路径：/uploads/ -> ../uploads/, uploads/ -> ../uploads/

    同时处理内部页面链接（如 contact.html -> ../contact.html）

    """

    if not path:

        return path

    if path.startswith('/uploads/'):

        return '../uploads/' + path[9:]

    if path.startswith('/pages/'):

        return '../pages/' + path[7:]

    if path.startswith('/static/'):

        return '../static/' + path[8:]

    if path.startswith('/'):

        # 其他以/开头的路径，检查是否是内部页面

        internal_pages = ('/index.html', '/about.html', '/activities.html',

                         '/resources.html', '/members.html', '/join.html', '/contact.html')

        if path in internal_pages:

            return '../' + path[1:]

        return path

    if path.startswith('uploads/') and not path.startswith('../'):

        return '../' + path

    # 处理 pages/ 同级的其他内部路径（static/ 等）

    if path.startswith('static/') and not path.startswith('../'):

        return '../' + path

    # 处理内部页面链接（如 index.html, about.html 等）

    if not path.startswith(('http://', 'https://', '#', 'mailto:', '../')):

        # 检查是否是内部 .html 页面

        internal_pages = ('index.html', 'about.html', 'activities.html',

                         'resources.html', 'members.html', 'join.html', 'contact.html')

        if path in internal_pages or path.startswith('pages/'):

            return '../' + path

    return path





def fix_path_for_root(path: str) -> str:

    """修复根目录页面中的路径：去掉开头的/使其变为相对路径

    /pages/aasd.html -> pages/aasd.html

    /uploads/xxx -> uploads/xxx

    """

    if not path:

        return path

    if path.startswith('/') and not path.startswith('//'):

        # 去掉开头的/使其变为相对路径（纯静态文件浏览兼容）

        if not path.startswith('/http'):

            return path[1:]

    return path





def load_data() -> Dict[str, Any]:

    """加载网站数据"""

    if os.path.exists(DATA_FILE):

        with open(DATA_FILE, 'r', encoding='utf-8') as f:

            return json.load(f)

    return {}



def parse_date(date_str: str) -> int:

    """解析日期字符串（YYYY年MM月DD日格式），返回整数便于比较"""

    if not date_str:

        return 0

    import re

    m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)

    if m:

        return int(m.group(1)) * 10000 + int(m.group(2)) * 100 + int(m.group(3))

    return 0





def ensure_dir(path: str) -> None:

    """确保目录存在"""

    os.makedirs(path, exist_ok=True)





# ==================== 导出器类 ====================



class SiteExporter:

    """静态网站导出器"""



    def __init__(self, output_dir: str = OUTPUT_DIR):

        self.output_dir = output_dir

        self.data = load_data()

        self.stats = {

            'total': 0,

            'success': 0,

            'failed': 0,

            'errors': []

        }



        # 初始化 Jinja2 环境

        self.env = Environment(

            loader=FileSystemLoader(TEMPLATE_DIR),

            autoescape=select_autoescape(['html', 'xml']),

            trim_blocks=True,

            lstrip_blocks=True

        )



        # 登记自定义过滤器

        self.env.filters['escape_html'] = escape_html

        self.env.filters['nl2br'] = nl2br

        self.env.filters['fix_uploads'] = fix_uploads_path

        self.env.filters['fix_uploads_pages'] = fix_uploads_path_for_pages

        self.env.filters['fix_path'] = fix_path_for_root



    def copy_static_files(self) -> None:

        """复制静态资源文件"""

        print("  Copying static files...")



        # 复制 static 目录

        static_out = os.path.join(self.output_dir, 'static')

        if os.path.exists(STATIC_DIR):

            if os.path.exists(static_out):

                shutil.rmtree(static_out)

            shutil.copytree(STATIC_DIR, static_out)



        # 复制 uploads 目录（成员头像等内链图片）

        uploads_dir = os.path.join(SITE_ROOT, 'uploads')

        uploads_out = os.path.join(self.output_dir, 'uploads')

        if os.path.exists(uploads_dir):

            if os.path.exists(uploads_out):

                shutil.rmtree(uploads_out)

            shutil.copytree(uploads_dir, uploads_out)

            print(f"    [OK] uploads folder copied ({len(os.listdir(uploads_dir))} files)")



        # 复制 css 目录

        css_out = os.path.join(self.output_dir, 'css')

        if os.path.exists(CSS_DIR):

            ensure_dir(css_out)

            for f in os.listdir(CSS_DIR):

                if f.endswith('.css'):

                    shutil.copy2(os.path.join(CSS_DIR, f), css_out)



        # 复制 js 目录（仅复制 main.js，data-loader.js 不随导出分发）

        js_out = os.path.join(self.output_dir, 'js')

        if os.path.exists(JS_DIR):

            ensure_dir(js_out)

            # 只复制main.js，data-loader不再需要

            main_js = os.path.join(JS_DIR, 'main.js')

            if os.path.exists(main_js):

                shutil.copy2(main_js, js_out)



        print("    [OK] Static files copied")



    def render_page_to_string(self, template_name: str, extra_data: Optional[Dict] = None) -> str:

        """渲染模板为字符串（不写入文件）"""

        template = self.env.get_template(template_name)

        render_data = {

            'data': self.data,

            'now': datetime.now(),

            'escape_html': escape_html,

            'nl2br': nl2br

        }

        if extra_data:

            render_data.update(extra_data)

        return template.render(**render_data)



    def render_page(self, template_name: str, output_name: str, extra_data: Optional[Dict] = None, post_process: Optional[callable] = None) -> bool:

        """渲染单个页面"""

        self.stats['total'] += 1



        try:

            template = self.env.get_template(template_name)

            render_data = {

                'data': self.data,

                'now': datetime.now(),

                'escape_html': escape_html,

                'nl2br': nl2br

            }

            if extra_data:

                render_data.update(extra_data)



            html = template.render(**render_data)



            if post_process:

                html = post_process(html)



            output_path = os.path.join(self.output_dir, output_name)

            with open(output_path, 'w', encoding='utf-8') as f:

                f.write(html)



            self.stats['success'] += 1

            print(f"    [OK] {output_name}")

            return True



        except Exception as e:

            self.stats['failed'] += 1

            self.stats['errors'].append(f"{output_name}: {str(e)}")

            print(f"    [FAIL] {output_name}: {str(e)}")

            return False



    def export_index(self) -> bool:

        """导出首页"""

        # 预处理：从 activities 取 visible=true 的最新3条

        activities = self.data.get('activities', [])

        visible = [a for a in activities if a.get('visible', True)]

        visible.sort(key=lambda x: parse_date(x.get('date', '')), reverse=True)

        latest_activities = visible[:3]



        return self.render_page(

            'index.html',

            'index.html',

            extra_data={'latest_activities': latest_activities}

        )



    def export_about(self) -> bool:

        """导出关于我们页面"""

        return self.render_page('about.html', 'about.html')



    def export_activities(self) -> bool:

        """导出星社动态页面"""

        # 预处理：从 activities 取 visible=true 的，按日期倒序

        activities = self.data.get('activities', [])

        visible = [a for a in activities if a.get('visible', True)]

        visible.sort(key=lambda x: parse_date(x.get('date', '')), reverse=True)



        return self.render_page(

            'activities.html',

            'activities.html',

            extra_data={'visible_activities': visible}

        )



    def export_members(self) -> bool:

        """导出成员页面"""

        # 预处理：只导出 visible=true 的成员，按排序顺序

        members = self.data.get('members', [])

        visible_members = [m for m in members if m.get('visible', True)]



        # 预处理：成果按日期倒序排列

        achievements = self.data.get('achievements', [])

        visible_achievements = [a for a in achievements if a.get('visible', True)]

        # 按日期排序（最新的在前）

        visible_achievements.sort(key=lambda x: x.get('date', ''), reverse=True)



        return self.render_page(

            'members.html',

            'members.html',

            extra_data={'visible_members': visible_members, 'sorted_achievements': visible_achievements}

        )



    def export_resources(self) -> bool:

        """导出资源页面"""

        # 预处理：只导出 visible=true 的资源，按类别分组

        resources = self.data.get('resources', [])

        visible_resources = [r for r in resources if r.get('visible', True)]



        # 按类别分组

        categories = {}

        for item in visible_resources:

            cat = item.get('category', '其他')

            if cat not in categories:

                categories[cat] = []

            categories[cat].append(item)



        return self.render_page(

            'resources.html',

            'resources.html',

            extra_data={'visible_resources': visible_resources, 'resource_categories': categories}

        )



    def export_join(self) -> bool:

        """导出加入星社页面"""

        return self.render_page('join.html', 'join.html')



    def export_contact(self) -> bool:

        """导出联系我们页面"""

        return self.render_page('contact.html', 'contact.html')



    def export_detail_pages(self) -> None:

        """导出所有详情页到 pages/ 子目录"""

        import copy

        detail_pages = self.data.get('detailPages', [])

        if not detail_pages:

            return

        # 导入markdown渲染（admin.py中已定义）

        try:

            from admin import render_markdown_content

        except ImportError:

            render_markdown_content = None



        # 确保 pages 子目录存在

        pages_dir = os.path.join(self.output_dir, 'pages')

        ensure_dir(pages_dir)



        for i, page in enumerate(detail_pages):

            # 深拷贝避免修改原始数据

            page = copy.deepcopy(page)

            # 预处理markdown板块 & 重命名items避免与dict.items()冲突

            for section in page.get('sections', []):

                if section.get('type') == 'markdown' and section.get('content'):

                    if render_markdown_content:

                        section['html'] = render_markdown_content(section['content'])

                if section.get('type') == 'cards' and 'items' in section:

                    section['card_items'] = section.pop('items')

            filename = page.get('filename', f'detail-{i}.html')

            # 保存到 pages/ 子目录（移除data-loader.js，内容已内嵌）

            self.render_page('detail.html', f'pages/{filename}', extra_data={'page': page},

                           post_process=lambda html: html.replace('<script src="../js/data-loader.js"></script>\n', '').replace('<script src="js/data-loader.js"></script>\n', ''))



    def export_all(self) -> Dict[str, Any]:

        """导出所有页面"""

        print("\n" + "=" * 50)

        print("StarClub Static Site Exporter v0.9")

        print("=" * 50)



        import tempfile

        staging_dir = tempfile.mkdtemp(prefix='export_staging_')

        try:

            # 清理并创建临时 staging 目录

            if os.path.exists(staging_dir):

                shutil.rmtree(staging_dir)

            ensure_dir(staging_dir)



            # 复制静态文件到 staging

            self.copy_static_files_to(staging_dir)



            # 导出所有页面到 staging

            original_output_dir = self.output_dir

            self.output_dir = staging_dir

            print("\n  Rendering pages:")

            self.export_index()

            self.export_about()

            self.export_activities()

            self.export_members()

            self.export_resources()

            self.export_join()

            self.export_contact()

            self.export_detail_pages()

            self.output_dir = original_output_dir



            # 从 staging 复制文件到实际输出目录

            print(f"\n  Copying files to: {self.output_dir}")

            self.copy_directory_tree(staging_dir, self.output_dir)

            print("  [OK] Files copied successfully")



        finally:

            # 清理 staging 目录

            if os.path.exists(staging_dir):

                shutil.rmtree(staging_dir)



        return {

            'success': self.stats['failed'] == 0,

            'stats': self.stats,

            'output_dir': self.output_dir

        }



    def copy_static_files_to(self, dest_dir: str):

        """复制静态文件到目标目录"""

        print("\n  Copying static files...")

        dirs_to_copy = [

            (STATIC_DIR, 'static'),

            (CSS_DIR, 'css'),

            (JS_DIR, 'js'),

            (os.path.join(SITE_ROOT, 'uploads'), 'uploads'),

        ]

        for src, name in dirs_to_copy:

            if os.path.exists(src):

                dest = os.path.join(dest_dir, name)

                if os.path.exists(dest):

                    shutil.rmtree(dest)

                shutil.copytree(src, dest)

                print(f"    [OK] {name} ({len(os.listdir(src))} files)")

            else:

                print(f"    [--] {name} (not found, skipped)")



    def copy_directory_tree(self, src: str, dest: str):

        """复制目录树到目标目录（逐文件覆盖，不删除目标文件）"""

        ensure_dir(dest)

        for item in os.listdir(src):

            src_item = os.path.join(src, item)

            dest_item = os.path.join(dest, item)

            if os.path.isdir(src_item):

                self.copy_directory_tree(src_item, dest_item)

            else:

                dest_subdir = os.path.dirname(dest_item)

                if dest_subdir and not os.path.exists(dest_subdir):

                    os.makedirs(dest_subdir, exist_ok=True)

                shutil.copy2(src_item, dest_item)



        # 输出统计

        print("\n" + "=" * 50)

        print("Export Complete!")

        print(f"  Total: {self.stats['total']}")

        print(f"  Success: {self.stats['success']}")

        print(f"  Failed: {self.stats['failed']}")

        print(f"  Output: {self.output_dir}")

        print("=" * 50)



        if self.stats['errors']:

            print("\nErrors:")

            for err in self.stats['errors']:

                print(f"  - {err}")



        return {

            'success': self.stats['failed'] == 0,

            'stats': self.stats,

            'output_dir': self.output_dir

        }



    def export_single(self, page: str) -> Dict[str, Any]:

        """导出单个页面"""

        pages = {

            'index': (self.export_index, 'index.html'),

            'about': (self.export_about, 'about.html'),

            'activities': (self.export_activities, 'activities.html'),

            'members': (self.export_members, 'members.html'),

            'resources': (self.export_resources, 'resources.html'),

            'join': (self.export_join, 'join.html'),

            'contact': (self.export_contact, 'contact.html'),

        }



        if page not in pages:

            return {

                'success': False,

                'error': f'未知页面: {page}',

                'available': list(pages.keys())

            }



        import tempfile

        staging_dir = tempfile.mkdtemp(prefix='export_single_')

        try:

            if os.path.exists(staging_dir):

                shutil.rmtree(staging_dir)

            ensure_dir(staging_dir)



            self.copy_static_files_to(staging_dir)



            original_output_dir = self.output_dir

            self.output_dir = staging_dir



            func, name = pages[page]

            func()



            self.output_dir = original_output_dir



            self.copy_directory_tree(staging_dir, self.output_dir)



            return {

                'success': self.stats['failed'] == 0,

                'stats': self.stats,

                'output_dir': self.output_dir

            }

        finally:

            if os.path.exists(staging_dir):

                shutil.rmtree(staging_dir)





# ==================== Flask API 集成 ====================



def add_export_routes(app):

    """为Flask应用添加导出路由"""

    from flask import jsonify, send_file

    import zipfile

    from io import BytesIO



    @app.route('/api/export', methods=['POST'])

    def api_export_all():

        """一键导出所有静态页面"""

        try:

            exporter = SiteExporter()

            result = exporter.export_all()



            if result['success']:

                return jsonify({

                    'success': True,

                    'message': '导出成功',

                    'output_dir': result['output_dir'],

                    'stats': result['stats']

                })

            else:

                return jsonify({

                    'success': False,

                    'message': '导出完成但有错误',

                    'errors': result['stats']['errors']

                }), 500



        except Exception as e:

            return jsonify({

                'success': False,

                'error': str(e)

            }), 500



    @app.route('/api/export/<page>', methods=['POST'])

    def api_export_page(page):

        """导出单个页面"""

        try:

            exporter = SiteExporter()

            result = exporter.export_single(page)



            if result.get('success'):

                return jsonify({

                    'success': True,

                    'message': f'{page} 导出成功',

                    'output': os.path.join(result['output_dir'], f'{page}.html')

                })

            else:

                return jsonify({

                    'success': False,

                    'error': result.get('error', '导出失败'),

                    'available': result.get('available', [])

                }), 400



        except Exception as e:

            return jsonify({

                'success': False,

                'error': str(e)

            }), 500



    @app.route('/api/export/download', methods=['GET'])

    def api_download_export():

        """下载导出的静态网站 ZIP 包"""

        try:

            exporter = SiteExporter()

            exporter.export_all()



            # 创建ZIP文件

            zip_buffer = BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:

                for root, dirs, files in os.walk(exporter.output_dir):

                    for file in files:

                        file_path = os.path.join(root, file)

                        arcname = os.path.relpath(file_path, exporter.output_dir)

                        zipf.write(file_path, arcname)



            zip_buffer.seek(0)

            filename = f'starclub-static-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'



            return send_file(

                zip_buffer,

                mimetype='application/zip',

                as_attachment=True,

                download_name=filename

            )



        except Exception as e:

            return jsonify({

                'success': False,

                'error': str(e)

            }), 500



    @app.route('/api/export/download-github', methods=['GET'])

    def api_download_github():

        """下载用于 GitHub Pages 的静态网站 ZIP 包（替换内部链接）

        只包含从 index.html 可达的文件（孤立页面不发布）

        """

        try:

            exporter = SiteExporter()

            exporter.export_all()



            import re



            # 定义需要替换的 URL 模式

            # 1. http://internal.host(...) - 原模式

            # 2. http(s)://internal.host(...) - 新增 HTTPS 支持

            # 3. http(s)://(任意子域名.)starclub.example.com(...) - 新增 starclub.example.com 域名

            url_pattern = re.compile(

                r'https?://(?:192\.168\.1\.x|(?:[\w-]+\.)*starclub\.example\.com)[^\s"\'<>)\]]*'

            )



            replace_to = 'pages/404.html'

            output_dir = exporter.output_dir



            # ========== 步骤1: 收集所有文件和内容（用于可达性分析） ==========

            # 先读取所有文件内容，分析时用原始内容

            file_contents = {}  # arcname -> content

            all_files = set()



            for root, dirs, files in os.walk(output_dir):

                for file in files:

                    file_path = os.path.join(root, file)

                    arcname = os.path.relpath(file_path, output_dir)

                    all_files.add(arcname)

                    if file.endswith('.html'):

                        with open(file_path, 'r', encoding='utf-8') as f:

                            file_contents[arcname] = f.read()



            # ========== 步骤2: 可达性分析（使用原始内容，404.html 可能被漏掉） ==========

            def extract_references(content, current_file):

                """从文件内容中提取所有引用（href, src, url 等）"""

                refs = set()

                base_dir = os.path.dirname(current_file)

                if base_dir:

                    base_dir += '/'



                for match in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', content):

                    refs.add(match.group(1))

                for match in re.finditer(r'src\s*=\s*["\']([^"\']+)["\']', content):

                    refs.add(match.group(1))

                for match in re.finditer(r'url\s*\(\s*["\']?([^"\')]+)["\']?\s*\)', content):

                    refs.add(match.group(1))

                for match in re.finditer(r'srcset\s*=\s*["\']([^"\']+)["\']', content):

                    for part in match.group(1).split(','):

                        part = part.strip().split()[0] if ' ' in part else part

                        if part:

                            refs.add(part)

                for match in re.finditer(r'action\s*=\s*["\']([^"\']+)["\']', content):

                    refs.add(match.group(1))



                resolved_refs = set()

                for ref in refs:

                    if ref.startswith('http://') or ref.startswith('https://') or ref.startswith('mailto:') or ref.startswith('#'):

                        continue

                    if ref.startswith('javascript:'):

                        continue

                    if ref.startswith('/'):

                        ref = ref.lstrip('/')

                    else:

                        ref = base_dir + ref

                    ref = os.path.normpath(ref).replace('\\', '/')

                    if not os.path.splitext(ref)[1]:

                        ref += '.html'

                    resolved_refs.add(ref)

                return resolved_refs



            # BFS 从 index.html 开始找可达文件

            reachable = set()

            queue = ['index.html']



            while queue:

                current = queue.pop(0)

                if current in reachable:

                    continue

                reachable.add(current)



                # 查找文件（尝试多种可能）

                current_paths = [current]

                if not os.path.splitext(current)[1]:

                    current_paths.append(current + '.html')

                    if '/' not in current:

                        current_paths.append('pages/' + current + '.html')



                current_path = None

                for cp in current_paths:

                    full_path = os.path.join(output_dir, cp)

                    if os.path.isfile(full_path):

                        current_path = full_path

                        break



                if current_path is None:

                    continue



                # 只分析 HTML 文件

                if current.endswith('.html') and current in file_contents:

                    content = file_contents[current]

                    refs = extract_references(content, current)

                    for ref in refs:

                        if ref not in reachable and ref in all_files:

                            queue.append(ref)



            # ========== 步骤3: 确保 pages/404.html 被包含（因为会被作为替换目标） ==========

            # 如果 404.html 存在但不在 reachable 中，强行加入

            if 'pages/404.html' in all_files:

                reachable.add('pages/404.html')



            # ========== 步骤4: 创建 ZIP（先替换链接） ==========

            zip_buffer = BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:

                for root, dirs, files in os.walk(output_dir):

                    for file in files:

                        file_path = os.path.join(root, file)

                        arcname = os.path.relpath(file_path, output_dir)



                        # 只包含可达文件

                        if arcname not in reachable:

                            continue



                        # 对 HTML 文件进行链接替换

                        if file.endswith('.html'):

                            content = file_contents.get(arcname)

                            if content:

                                content = url_pattern.sub(replace_to, content)

                            else:

                                with open(file_path, 'r', encoding='utf-8') as f:

                                    content = f.read()

                                content = url_pattern.sub(replace_to, content)

                            zipf.writestr(arcname, content.encode('utf-8'))

                        else:

                            zipf.write(file_path, arcname)



            zip_buffer.seek(0)

            filename = f'starclub-github-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'



            return send_file(

                zip_buffer,

                mimetype='application/zip',

                as_attachment=True,

                download_name=filename

            )



        except Exception as e:

            return jsonify({

                'success': False,

                'error': str(e)

            }), 500





# ==================== 入口 ====================



if __name__ == '__main__':

    import argparse



    parser = argparse.ArgumentParser(description='StarClub 静态网站导出器')

    parser.add_argument('--page', '-p', type=str, help='导出单个页面 (index/about/activities/members/resources/join/contact)')

    parser.add_argument('--output', '-o', type=str, default=OUTPUT_DIR, help='输出目录')



    args = parser.parse_args()



    exporter = SiteExporter(output_dir=args.output)



    if args.page:

        exporter.export_single(args.page)

    else:

        exporter.export_all()
