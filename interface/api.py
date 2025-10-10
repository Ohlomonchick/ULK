import json
import requests
import urllib3
import logging
import random

from interface.utils import get_kibana_url

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta, datetime
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST


from .models import Competition, LabLevel, Lab, LabTask, Answers, User, TeamCompetition, LabTasksType, Kkz
from .serializers import LabLevelSerializer, LabTaskSerializer
from .api_utils import get_issue
from .config import get_pnet_base_dir, get_pnet_url, get_web_url
from .utils import get_pnet_lab_name


@api_view(['GET'])
def get_time(request, competition_id):  # pragma: no cover
    try:
        # Fetch the competition by ID
        competition = Competition.objects.get(id=competition_id)

        # Calculate remaining time
        remaining_time = competition.finish - timezone.now()
        if remaining_time < timedelta(0):
            remaining_time = timedelta(0)

        hours, remainder = divmod(remaining_time.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return Response({
            'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
        })
    except Competition.DoesNotExist:
        return Response({'error': 'Competition not found'}, status=404)


def make_solution_data(solution, competition):
    user = User.objects.get(pk=solution["user_id"])
    return {
        "pos": 0,
        "user_first_name": user.first_name,
        "user_last_name": user.last_name,
        "user_platoon": str(user.platoon),
        "spent": str(solution["datetime"] - competition.start).split(".")[0] if solution["datetime"] else "",
        "datetime": solution["datetime"].strftime("%H:%M:%S") if solution["datetime"] else "",
        "raw_datetime": solution["datetime"],
        "team_name": "",
        "user_id": solution["user_id"]
    }


@api_view(['GET'])
def get_solutions(request, slug):
    try:
        competition = TeamCompetition.objects.get(slug=slug)
    except TeamCompetition.DoesNotExist:
        competition = get_object_or_404(Competition, slug=slug)
    total_tasks = competition.tasks.count()
    is_team_competition = hasattr(competition, 'teams')

    all_individual_users = User.objects.filter(
        platoon__in=competition.platoons.all()) | competition.non_platoon_users.all()
    if is_team_competition:
        team_user_ids = User.objects.filter(team__in=competition.teams.all()).values_list("id", flat=True)
        all_individual_users = all_individual_users.exclude(id__in=team_user_ids)

    individual_filter = Q(user__isnull=False) & (
            Q(user__platoon__in=competition.platoons.all()) |
            Q(user__in=competition.non_platoon_users.all())
    )
    individual_answers_qs = Answers.objects.filter(
        individual_filter,
        lab=competition.lab,
        datetime__lte=competition.finish,
        datetime__gte=competition.start
    )

    # 2a. If team competition, also query team answers.
    team_answers_qs = Answers.objects.none()
    if is_team_competition:
        team_answers_qs = Answers.objects.filter(
            team__in=competition.teams.all(),
            lab=competition.lab,
            datetime__lte=competition.finish,
            datetime__gte=competition.start,
            team__isnull=False
        )

    individual_data = {}
    for answer in individual_answers_qs:
        uid = answer.user.id
        if uid not in individual_data:
            individual_data[uid] = {
                'answers': [],
                'progress': 0,
                'raw_datetime': answer.datetime
            }
        individual_data[uid]['answers'].append(answer)
        if total_tasks > 0:
            individual_data[uid]['progress'] = len(individual_data[uid]['answers'])
        else:
            individual_data[uid]['progress'] = 1  # if lab has no tasks, a single answer gives progress 1.
        if answer.datetime > individual_data[uid]['raw_datetime']:
            individual_data[uid]['raw_datetime'] = answer.datetime

    for user in all_individual_users:
        if user.id not in individual_data:
            individual_data[user.id] = {
                'answers': [],
                'progress': 0,
                'raw_datetime': None
            }

    solutions_data = []
    # Create solution entries for individual answers.
    for uid, data in individual_data.items():
        dummy_solution = {
            "user_id": uid,
            "datetime": data['raw_datetime']
        }
        sol = make_solution_data(dummy_solution, competition)
        sol["progress"] = data['progress']
        solutions_data.append(sol)

    # 4. Process team answers if applicable – group by team.
    if is_team_competition:
        team_data = {}
        for answer in team_answers_qs:
            tid = answer.team.id
            if tid not in team_data:
                team_data[tid] = {
                    'answers': [],
                    'progress': 0,
                    'raw_datetime': answer.datetime,
                    'team': answer.team
                }
            team_data[tid]['answers'].append(answer)
            if total_tasks > 0:
                team_data[tid]['progress'] = len(team_data[tid]['answers'])
            else:
                team_data[tid]['progress'] = 1
            if answer.datetime > team_data[tid]['raw_datetime']:
                team_data[tid]['raw_datetime'] = answer.datetime

        for team in competition.teams.all():
            if team.id not in team_data:
                team_data[team.id] = {
                    'answers': [],
                    'progress': 0,
                    'raw_datetime': None,
                    'team': team
                }

        # For every team, create a solution entry for each member.
        for tid, data in team_data.items():
            team_obj = data['team']
            for user in team_obj.users.all():
                dummy_solution = {
                    "user_id": user.id,
                    "datetime": data['raw_datetime']
                }
                sol = make_solution_data(dummy_solution, competition)
                sol["progress"] = data['progress']
                sol["team_name"] = team_obj.name
                solutions_data.append(sol)

    # 5. Sorting: sort first by progress (descending), then by team_name (if present) and by submission time.
    solutions_data.sort(key=lambda x: (-x["progress"], x["raw_datetime"], x["team_name"]))

    # Re-assign positions based on sorted order.
    pos = 1
    for sol in solutions_data:
        sol["pos"] = pos
        pos += 1

    # 3.a. If lab has tasks, include the total_tasks in the JSON.
    response = {
        "solutions": solutions_data,
        "max_total_progress": competition.participants,
        "total_progress":  sum(solution["progress"] for solution in solutions_data),
        "total_tasks": 1
    }
    if total_tasks:
        response["max_total_progress"] = competition.participants * total_tasks
        response["total_tasks"] = total_tasks
    return JsonResponse(response)


@api_view(['GET'])
def load_levels(request, lab_name):  # pragma: no cover
    try:
        # Сначала пытаемся найти по slug, затем по name
        try:
            lab = Lab.objects.get(slug=lab_name)
        except Lab.DoesNotExist:
            lab = Lab.objects.get(name=lab_name)
        levels = LabLevel.objects.filter(lab=lab)
        serializer = LabLevelSerializer(levels, many=True)
        return Response(serializer.data)
    except Lab.DoesNotExist:
        return Response({"error": "Lab not found"}, status=404)


@api_view(['GET'])
def load_tasks(request, lab_name):  # pragma: no cover
    try:
        # Сначала пытаемся найти по slug, затем по name
        try:
            lab = Lab.objects.get(slug=lab_name)
        except Lab.DoesNotExist:
            lab = Lab.objects.get(name=lab_name)
        tasks = LabTask.objects.filter(lab=lab)
        serializer = LabTaskSerializer(tasks, many=True)
        return Response(serializer.data)
    except Lab.DoesNotExist:
        return Response({"error": "Lab not found"}, status=404)


def change_iso_timezone(utc_time):  # pragma: no cover
    print(utc_time)
    if utc_time[-1] == 'Z':
        utc_time = utc_time[:-1]
    return datetime.fromisoformat(utc_time) + timedelta(hours=3)


@api_view(['POST'])
def press_button(request, action):  # pragma: no cover
    try:
        slug = request.data.get('slug')
        competition = Competition.objects.get(
            slug=slug
        )
        competition_url = reverse('interface:competition-detail', kwargs={'slug': slug})
        if action == "start":
            competition.start = timezone.now()
            competition.save()
            cache.set("competitions_update", True, timeout=60)
            return JsonResponse({"redirect_url": competition_url}, status=200)
        elif action == "end":
            competition.finish = timezone.now()
            competition.save()
            cache.set("competitions_update", True, timeout=60)
            return JsonResponse({"message": "Competition ended", "redirect_url": competition_url}, status=200)
        elif action == "resume":
            competition.finish = timezone.now() + timedelta(minutes=15)
            competition.save()
            cache.set("competitions_update", True, timeout=60)
            return JsonResponse({"message": "Competition resumed", "redirect_url": competition_url}, status=200)
        else:
            return JsonResponse({"error": "Unknown action"}, status=400)

    except Exception as e:
        print(f"Server error: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@api_view(['GET'])
def check_updates(request):  # pragma: no cover
    last_update = cache.get("competitions_update", False)
    if last_update:
        cache.delete("competitions_update")
    return JsonResponse({"update_required": last_update})


@api_view(['GET'])
def check_availability(request, slug):  # pragma: no cover
    try:
        competition = Competition.objects.get(slug=slug)
        available = competition.finish > timezone.now()
        return JsonResponse({"available": available})
    except Competition.DoesNotExist:
        return JsonResponse({"error": "Competition not found"}, status=404)


@api_view(['GET'])
def get_users_in_platoons(request):  # pragma: no cover
    platoon_ids = request.GET.get('platoons', '')

    if platoon_ids:
        ids = [int(x) for x in platoon_ids.split(',') if x.isdigit()]
        users = User.objects.filter(platoon__number__in=ids).order_by('username')
        print(users)
        data = [{"id": user.pk, "login": user.username} for user in users]
    else:
        data = []
    return JsonResponse(data, safe=False)


def create_var_text(second_name):
    new_var = rf"""/testdir/ 1 1 1 1 1 1 1 1 1 1
./ {second_name}d1 drwxrwxrwxm-- admin admin Секретно:Низкий:Нет:0x0
{second_name}d1/ {second_name}d2 drwxrwx---m-- admin admin Секретно:Низкий:Нет:0x0
{second_name}d1/ {second_name}f1 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0
{second_name}d1/ {second_name}f3 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0"""
    return new_var


def parse_request_data(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (ValueError, TypeError):
        raise


def gey_lab_tasks(issue):
    if issue.competition.lab.tasks_type == LabTasksType.CLASSIC:
        tasks = [task.task_id for task in issue.competition.tasks.all()]
    else:
        tasks = [{'id': task.task_id, **task.json_config} for task in issue.competition.tasks.all()]
    return tasks


@api_view(['GET'])
def start_lab(request):
    if request.method == 'GET':
        issue, error_response = get_issue(
            parse_request_data(request),
            {'competition__finish__gt': timezone.now()}
        )
        logging.info(f"payload: {parse_request_data(request)}")
        if error_response:
            return error_response

        response_data = {
            "tasks": gey_lab_tasks(issue)
        }
        if hasattr(issue, 'user'):
            response_data["task"] = create_var_text(issue.user.last_name),
        if hasattr(issue, 'level') and issue.level:
            response_data["variant"] = issue.level.level_number
        if issue.competition.lab.answer_flag:
            response_data["flag"] = issue.competition.lab.answer_flag
        if hasattr(issue, 'team') and issue.team:
            response_data["team"] = [user.pnet_login for user in issue.team.users.all()]
        response_data["type"] = issue.competition.lab.lab_type
        return JsonResponse(response_data)


@api_view(['POST'])
def end_lab(request):
    if request.method == 'POST':
        issue, error_response = get_issue(
            parse_request_data(request),
            {'competition__start__lt': timezone.now()}
        )
        if error_response:
            return error_response

        if issue.tasks.count() > 0:
            return JsonResponse({'message': 'Task finished'})

        if hasattr(issue, 'user'):
            Answers.objects.update_or_create(
                lab=issue.competition.lab, 
                user=issue.user,
                lab_task=None,
                defaults={'datetime': timezone.now()}
            )
        elif hasattr(issue, 'team'):
            Answers.objects.update_or_create(
                lab=issue.competition.lab,
                team=issue.team,
                lab_task=None,
                defaults={'datetime': timezone.now()}
            )

        return JsonResponse({'message': 'Task finished'})


@csrf_exempt
@api_view(['POST'])
def get_pnet_auth(request):
    """Аутентифицирует пользователя в PNET и возвращает cookies"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)

    user = request.user
    if not user.pnet_login or not user.pnet_password:
        return JsonResponse({'error': 'User PNET credentials not configured'}, status=400)

    try:
        pnet_url = f"{get_web_url()}/pnetlab"
        session = requests.Session()
        session.verify = False

        # Получаем XSRF-TOKEN
        preflight_response = session.get(f"{pnet_url}/store/public/auth/login/login", timeout=10)
        if preflight_response.status_code not in [200, 202]:
            return JsonResponse({'error': 'Failed to connect to PNET'}, status=500)

        xsrf_token = session.cookies.get('XSRF-TOKEN', '')

        # Аутентификация
        headers = {'Content-Type': 'application/json;charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest'}
        if xsrf_token:
            headers['X-XSRF-TOKEN'] = xsrf_token

        login_response = session.post(
            f"{pnet_url}/store/public/auth/login/login",
            headers=headers,
            json={'username': user.pnet_login, 'password': user.pnet_password, 'html': '1', 'captcha': ''},
            timeout=10
        )

        if login_response.status_code not in [200, 201, 202]:
            return JsonResponse({'error': 'PNET authentication failed'}, status=401)

        # Проверка JSON ответа для статуса 202
        if login_response.status_code == 202:
            try:
                if not login_response.json().get('result', False):
                    return JsonResponse({'error': 'PNET authentication failed'}, status=401)
            except (ValueError, KeyError):
                pass  # Продолжаем, возможно cookies установлены

        # Возвращаем cookies и устанавливаем их в ответе
        cookies_dict = {cookie.name: cookie.value for cookie in session.cookies}
        response = JsonResponse({'success': True, 'cookies': cookies_dict, 'xsrf_token': xsrf_token})

        # Устанавливаем cookies в HTTP-ответе для автоматической синхронизации
        logger = logging.getLogger(__name__)

        for cookie in session.cookies:
            logger.info(f"Setting cookie {cookie.name}={cookie.value} domain={cookie.domain} path={cookie.path}")
            response.set_cookie(
                cookie.name,
                cookie.value,
                path='/',  # Принудительно устанавливаем корневой путь
                secure=False,  # Отключаем secure для HTTP
                httponly=False,  # Разрешаем JavaScript доступ
                samesite='Lax'
            )

        return response

    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'PNET request timeout'}, status=500)
    except requests.exceptions.ConnectionError:
        return JsonResponse({'error': 'Failed to connect to PNET'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Authentication error: {str(e)}'}, status=500)


@api_view(['GET'])
def check_kibana_auth_status(request):
    """Проверяет статус аутентификации пользователя в Kibana"""
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated': False, 'error': 'User not authenticated'}, status=401)

    user = request.user
    if not user.pnet_login or not user.pnet_password:
        return JsonResponse({'authenticated': False, 'error': 'User credentials not configured'}, status=400)

    try:
        kibana_url = get_kibana_url()
        session = requests.Session()
        session.verify = False

        # Проверяем статус аутентификации через API Kibana
        headers = {
            'Accept': 'application/json',
            'kbn-version': '9.1.2',
            'x-elastic-internal-origin': 'Kibana'
        }

        # Пробуем получить информацию о текущем пользователе
        status_response = session.get(
            f"{kibana_url}/internal/security/me",
            headers=headers,
            timeout=5
        )

        # Если получили 200 - пользователь аутентифицирован
        if status_response.status_code == 200:
            try:
                user_info = status_response.json()
                return JsonResponse({
                    'authenticated': True,
                    'username': user_info.get('username', user.pnet_login)
                })
            except (ValueError, KeyError):
                pass

        # Если получили 401/403 - пользователь не аутентифицирован
        return JsonResponse({'authenticated': False})

    except requests.exceptions.Timeout:
        return JsonResponse({'authenticated': False, 'error': 'Kibana request timeout'}, status=500)
    except requests.exceptions.ConnectionError:
        return JsonResponse({'authenticated': False, 'error': 'Failed to connect to Kibana'}, status=500)
    except Exception as e:
        return JsonResponse({'authenticated': False, 'error': f'Check error: {str(e)}'}, status=500)


@csrf_exempt
@api_view(['POST'])
def get_kibana_auth(request):
    """Аутентифицирует пользователя в Kibana и возвращает cookies"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)

    user = request.user
    if not user.pnet_login or not user.pnet_password:
        return JsonResponse({'error': 'User credentials not configured'}, status=400)

    try:
        kibana_url = get_kibana_url()
        session = requests.Session()
        session.verify = False

        # Получаем главную страницу Kibana для получения версии
        main_page_response = session.get(f"{kibana_url}/", timeout=10)
        if main_page_response.status_code not in [200, 401, 403]:
            return JsonResponse({'error': 'Failed to connect to Kibana'}, status=500)

        # Извлекаем версию Kibana из заголовков
        kbn_version = main_page_response.headers.get('kbn-version', '9.1.2')

        # Аутентификация через внутренний API Kibana
        headers = {
            'Content-Type': 'application/json',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'ru,en;q=0.9',
            'Connection': 'keep-alive',
            'Origin': kibana_url,
            'Referer': f"{kibana_url}/login?msg=LOGGED_OUT",
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 YaBrowser/25.8.0.0 Safari/537.36',
            'kbn-build-number': '88427',
            'kbn-version': kbn_version,
            'x-elastic-internal-origin': 'Kibana'
        }

        login_data = {
            'providerType': 'basic',
            'providerName': 'basic',
            'currentURL': f"{kibana_url}/login?msg=LOGGED_OUT",
            'params': {
                'username': user.pnet_login,
                'password': user.pnet_password
            }
        }

        login_response = session.post(
            f"{kibana_url}/internal/security/login",
            headers=headers,
            json=login_data,
            timeout=10
        )

        if login_response.status_code not in [200, 201, 202]:
            return JsonResponse({'error': 'Kibana authentication failed'}, status=401)

        # Проверяем успешность аутентификации
        try:
            login_result = login_response.json()
            if not login_result.get('success', True):
                return JsonResponse({'error': 'Kibana authentication failed'}, status=401)
        except (ValueError, KeyError):
            pass  # Продолжаем, возможно cookies установлены

        # Возвращаем cookies и устанавливаем их в ответе
        cookies_dict = {cookie.name: cookie.value for cookie in session.cookies}
        response = JsonResponse({'success': True, 'cookies': cookies_dict})

        # Устанавливаем cookies в HTTP-ответе для автоматической синхронизации
        for cookie in session.cookies:
            response.set_cookie(
                cookie.name,
                cookie.value,
                path='/',
                secure=False,
                httponly=False,
                samesite='Lax'
            )

        return response

    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Kibana request timeout'}, status=500)
    except requests.exceptions.ConnectionError:
        return JsonResponse({'error': 'Failed to connect to Kibana'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Kibana authentication error: {str(e)}'}, status=500)


@csrf_exempt
@api_view(['POST'])
def create_pnet_lab_session(request):
    """Создает сессию лабы в PNET после аутентификации"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)

    slug = request.data.get('slug')
    if not slug:
        return JsonResponse({'error': 'Competition slug required'}, status=400)

    try:
        competition = Competition.objects.get(slug=slug)
        user = request.user

        if not user.pnet_login:
            return JsonResponse({'error': 'User PNET login not configured'}, status=400)

        base_path = get_pnet_base_dir()
        lab_name = get_pnet_lab_name(competition)
        lab_file_name = lab_name + '.unl'
        lab_path = f"/{base_path.rstrip('/').lstrip('/')}/{user.pnet_login}/{lab_file_name}"

        # Отправляем запрос на создание сессии лабы
        pnet_url = f"{get_web_url()}/pnetlab"
        session = requests.Session()
        session.verify = False

        # Копируем cookies из запроса (должны быть установлены после аутентификации)
        for cookie_name, cookie_value in request.COOKIES.items():
            session.cookies.set(cookie_name, cookie_value)

        # Используем общую логику создания сессии
        from .eveFunctions import create_pnet_lab_session_common
        success, message = create_pnet_lab_session_common(pnet_url, user.pnet_login, lab_path, session.cookies)
        
        if not success:
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create lab session: {message}")
            return JsonResponse({'error': message}, status=500)

        return JsonResponse({
            'success': True,
            'lab_path': lab_path,
            'redirect_url': '/legacy/topology'
        })

    except Competition.DoesNotExist:
        return JsonResponse({'error': 'Competition not found'}, status=404)
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'PNET request timeout'}, status=500)
    except requests.exceptions.ConnectionError:
        return JsonResponse({'error': 'Failed to connect to PNET'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Session creation error: {str(e)}'}, status=500)


@csrf_exempt
@api_view(['POST'])
def create_pnet_lab_session_with_console(request):
    """Создает сессию лабы в PNET и возвращает ссылку на консоль SSH ноды"""
    slug = request.data.get('slug')
    if not slug:
        return JsonResponse({'error': 'Competition slug required'}, status=400)
    
    # Получаем node_name из request.data, если не указан - используем PnetSSHNodeName
    node_name = request.data.get('node_name')
    
    # Получаем username из request.data, если не передан - используем request.user
    username = request.data.get('username')
    if not username:
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Username required or user must be authenticated'}, status=400)
        username = request.user.username

    try:
        logger = logging.getLogger(__name__)
        logger.info(f'Creating CMD console session for slug: {slug}, username: {username}')
        
        competition = Competition.objects.get(slug=slug)
        
        # Получаем пользователя по username
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Fallback: попробуем найти по pnet_login
            try:
                user = User.objects.get(pnet_login=username)
            except User.DoesNotExist:
                return JsonResponse({'error': f'User with username "{username}" not found'}, status=404)
        
        # Если node_name не передан в запросе, используем PnetSSHNodeName из лабы
        if not node_name:
            node_name = competition.lab.PnetSSHNodeName
        
        logger.info(f'Competition found: {competition}, Lab: {competition.lab}, SSH Node: {node_name}')

        if not user.pnet_login or not user.pnet_password:
            logger.error(f'User PNET credentials not configured for user: {user}')
            return JsonResponse({'error': 'User PNET credentials not configured'}, status=400)

        if not node_name:
            logger = logging.getLogger(__name__)
            logger.error(f'SSH node name not configured for lab: {competition.lab}')
            return JsonResponse({'error': 'SSH node name not configured for this lab'}, status=400)

        # Импортируем функции из eveFunctions
        from .eveFunctions import pf_login, create_pnet_lab_session_common, get_lab_topology, get_guacamole_url, turn_on_node

        # Получаем URL PNET
        pnet_url = get_pnet_url()
        
        # Логинимся в PNET
        cookies, xsrf_token = pf_login(pnet_url, user.pnet_login, user.pnet_password)
        
        # Получаем путь до лабы пользователя
        base_path = get_pnet_base_dir()
        lab_name = get_pnet_lab_name(competition)
        lab_file_name = lab_name + '.unl'
        lab_path = f"/{base_path.rstrip('/').lstrip('/')}/{user.pnet_login}/{lab_file_name}"

        # Создаем сессию лабы
        success, message = create_pnet_lab_session_common(pnet_url, user.pnet_login, lab_path, cookies)
        if not success:
            return JsonResponse({'error': message}, status=500)

        # Получаем топологию лаборатории
        topology = get_lab_topology(pnet_url, cookies)
        if not topology or topology.get('code') != 200:
            return JsonResponse({'error': 'Failed to get lab topology'}, status=500)

        # Ищем ноду по имени
        nodes = topology.get('data', {}).get('nodes', {})
        target_node_id = None
        
        for node_id, node_data in nodes.items():
            if node_data.get('name') == node_name:
                target_node_id = int(node_id)
                break

        if target_node_id is None:
            return JsonResponse({'error': f'SSH node "{node_name}" not found in topology'}, status=404)

        # Включаем ноду перед получением ссылки на консоль
        logger.info(f'Starting node {target_node_id}...')
        node_start_success, node_start_message = turn_on_node(pnet_url, target_node_id, cookies)
        if not node_start_success:
            logger.error(f'Failed to start node: {node_start_message}')
            return JsonResponse({'error': f'Failed to start node: {node_start_message}'}, status=500)

        # Получаем ссылку на Guacamole консоль
        guacamole_url = get_guacamole_url(pnet_url, target_node_id, cookies)
        if not guacamole_url:
            return JsonResponse({'error': 'Failed to get console URL'}, status=500)

        return JsonResponse({
            'success': True,
            'node_id': target_node_id,
            'node_name': node_name,
            'guacamole_url': guacamole_url,
            'lab_path': lab_path
        })

    except Competition.DoesNotExist:
        return JsonResponse({'error': 'Competition not found'}, status=404)
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'PNET request timeout'}, status=500)
    except requests.exceptions.ConnectionError:
        return JsonResponse({'error': 'Failed to connect to PNET'}, status=500)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f'Console session creation error: {str(e)}')
        return JsonResponse({'error': f'Console session creation error: {str(e)}'}, status=500)


@require_POST
def kkz_preview_random(request):
    lab_id = request.GET.get('lab_id')
    num_tasks_str = request.GET.get('num_tasks', '0')
    count_str = request.GET.get('count', '1')

    try:
        num_tasks = int(num_tasks_str)
        count = int(count_str)
    except ValueError:
        return JsonResponse({'error': 'Invalid parameters'}, status=400)

    if num_tasks <= 0:
        return JsonResponse({'sets': [[] for _ in range(count)] if count > 1 else {'tasks': []}})

    try:
        lab = Lab.objects.get(id=lab_id)
    except Lab.DoesNotExist:
        return JsonResponse({'error': 'Lab not found'}, status=400)

    all_tasks = list(lab.options.all())
    if len(all_tasks) < num_tasks:
        return JsonResponse({'error': 'Not enough tasks'}, status=400)

    sets = []
    for _ in range(count):
        sampled = random.sample(all_tasks, num_tasks)
        sets.append([t.id for t in sampled])

    if count == 1:
        return JsonResponse({'tasks': sets[0]})
    else:
        return JsonResponse({'sets': sets})


@require_GET
def kkz_preview_random(request):
    lab_id = request.GET.get("lab_id")
    num_tasks = int(request.GET.get("num_tasks", 0) or 0)
    unified = request.GET.get("unified", "false").lower() in ("1", "true", "yes", "on")
    platoon_ids = request.GET.get("platoon_ids")
    user_ids = request.GET.get("user_ids")
    kkz_id = request.GET.get("kkz_id")
    force_regen = request.GET.get("force_regen", "false").lower() in ("1", "true", "yes", "on")

    selected_task_ids = request.GET.get("selected_tasks")

    if platoon_ids:
        platoon_ids = [int(x) for x in platoon_ids.split(",") if x.strip()]
    else:
        platoon_ids = None

    if user_ids:
        user_ids = [int(x) for x in user_ids.split(",") if x.strip()]
    else:
        user_ids = None

    if selected_task_ids:
        selected_task_ids = [int(x) for x in selected_task_ids.split(",") if x.strip()]
    else:
        selected_task_ids = None

    lab = get_object_or_404(Lab, id=lab_id)
    all_tasks = list(LabTask.objects.filter(lab=lab, id__in=selected_task_ids).order_by('id'))
    tasks_json = [{"id": t.id, "description": getattr(t, "description", str(t))} for t in all_tasks]
    task_ids_set = {t.id for t in all_tasks}

    if kkz_id:
        kkz = get_object_or_404(Kkz, id=kkz_id)
        users = list(kkz.get_users())
        unified = kkz.unified_tasks
    else:
        users = set()
        if platoon_ids:
            users.update(User.objects.filter(platoon__in=platoon_ids))
        if user_ids:
            users.update(User.objects.filter(id__in=user_ids))
        users = list(users)

    users = sorted(users, key=lambda u: u.get_full_name() or u.username)
    users_json = [{"id": u.id, "username": u.username, "display": u.get_full_name() or u.username} for u in users]

    assignments = {}
    regenerate = force_regen

    if kkz_id and not force_regen:
        previews = KkzPreview.objects.filter(kkz=kkz, lab=lab)
        previews_dict = {p.user.id: p for p in previews}
        missing_users = [u for u in users if u.id not in previews_dict]
        invalid_previews = False
        for user_id, preview in previews_dict.items():
            preview_task_ids = {t.id for t in preview.tasks.all()}
            if not preview_task_ids.issubset(task_ids_set):
                invalid_previews = True
                break

        if missing_users or invalid_previews or previews.count() != len(users):
            regenerate = True
        else:
            assignments = {str(u.id): [t.id for t in previews_dict[u.id].tasks.all()] for u in users}

    if regenerate or not kkz_id:
        assignments = {}
        if users:
            if unified:
                picked = random.sample(all_tasks, min(num_tasks, len(all_tasks)))
                p_ids = [t.id for t in picked]
                for u in users:
                    assignments[str(u.id)] = p_ids
            else:
                for u in users:
                    sel = random.sample(all_tasks, min(num_tasks, len(all_tasks)))
                    assignments[str(u.id)] = [t.id for t in sel]

    return JsonResponse({
        "lab": {"id": lab.id, "name": lab.name},
        "tasks": tasks_json,
        "users": users_json,
        "assignments": assignments
    })


@require_POST
def kkz_save_preview(request):
    data = json.loads(request.body)
    kkz_id = data.get('kkz_id')
    lab_id = data.get('lab_id')
    assignments = data.get('assignments', {})

    print(f"kkz_save_preview called: kkz_id={kkz_id}, lab_id={lab_id}, assignments={assignments}")

    kkz = get_object_or_404(Kkz, id=kkz_id)
    lab = get_object_or_404(Lab, id=lab_id)

    if kkz.unified_tasks:
        if assignments:
            first_user_id = next(iter(assignments))
            uniform_task_ids = assignments[first_user_id]
            users = kkz.get_users()
            for user in users:
                preview, created = KkzPreview.objects.update_or_create(
                    kkz=kkz,
                    lab=lab,
                    user=user,
                    defaults={}
                )
                preview.tasks.set(uniform_task_ids)
    else:
        for user_id_str, task_ids in assignments.items():
            try:
                user_id = int(user_id_str)
                user = get_object_or_404(User, id=user_id)
                preview, created = KkzPreview.objects.update_or_create(
                    kkz=kkz,
                    lab=lab,
                    user=user,
                    defaults={}
                )
                preview.tasks.set(task_ids)
            except (ValueError, User.DoesNotExist):
                continue

    return JsonResponse({'status': 'ok'})
