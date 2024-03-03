from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
import logging
from interface.models import Lab, Answers, User, Platoon, IssuedLabs
from interface.forms import LabAnswerForm

from django.contrib.auth import login, authenticate
from interface.forms import SignUpForm
from django.shortcuts import render, redirect


class LabDetailView(DetailView):
    model = Lab

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = LabAnswerForm()
        context["submitted"] = False
        if self.request.user.is_authenticated:
            answered = Answers.objects.filter(lab=context["object"], user=self.request.user).first()
            issuedLab = IssuedLabs.objects.filter(lab=context["object"], user=self.request.user).first()
            if answered is None:
                answer = self.request.GET.get("answer_flag")
                if answer:
                    if answer == context["object"].answer_flag:
                        context["submitted"] = True
                        answer_object = Answers(lab=context["object"], user=self.request.user)
                        issuedLab.done = True
                        issuedLab.save()
                        answer_object.save()
                    else:
                        context["form"].fields["answer_flag"].label = "Неверный флаг!"
            else:
                context["submitted"] = True

        return context


class LabListView(ListView):
    model = Lab

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.user.is_superuser:
            labs = []
            issues = IssuedLabs.objects.filter(user = self.request.user).exclude(done = True)
            for issue in issues:
                labs.append(issue.lab)
            labs_set = set(labs)
            object_list = labs_set
            context["object_list"] = object_list
        logging.debug(context)
        return context


class PlatoonDetailView(DetailView):
    model = Platoon
    pk_url_kwarg = 'id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_list = User.objects.filter(platoon = context["platoon"]).exclude(username = "admin")
        context["user_list"] = user_list
        competitions ={}
        comps = Competition.objects.filter(platoons = context["platoon"])
        for comp in comps:
            if (comp.finish - timezone.now()).seconds < 0:
                competitions[comp] = False
            else: 
                competitions[comp] = True
        context["competitions"] = competitions
        logging.debug(context)
        logging.debug(competitions)
        return context


class PlatoonListView(ListView):
    model = Platoon

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        platoons_progress = {}
        for platoon in context["object_list"]:
            platoons_progress[platoon] = {"total":0, "submitted":0, "progress":0}
            user_list = User.objects.filter(platoon = platoon).exclude(username = "admin")
            for user in user_list:
                platoons_progress[platoon]["total"] += len(IssuedLabs.objects.filter(user = user))
                platoons_progress[platoon]["submitted"] += len(IssuedLabs.objects.filter(user = user).exclude(done = False))
                platoons_progress[platoon]["progress"] += int(platoons_progress[platoon]["submitted"] / platoons_progress[platoon]["total"]) * 100
        context["object_list"] = platoons_progress
        logging.debug(context)
        return context


class UserDetailView(DetailView):
    model = User
    pk_url_kwarg = 'id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = User.objects.filter(username = "admin").first()
        labs = []
        issues = IssuedLabs.objects.filter(user = context["object"])
        object_list = issues
        context["object_list"] = object_list
        total = len(issues)
        context["total"] = total
        submitted = len(IssuedLabs.objects.filter(user = context["object"]).exclude(done = False))
        context["submitted"] = submitted
        progress = int((submitted / total) * 100)
        context["progress"] = progress
        logging.debug(context)
        return context


def registration(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        platoon = int(request.POST.get('platoon'))
        if not Platoon.objects.filter(id = platoon).exists():
            Platoon.objects.create(id = platoon)
        platoon = Platoon.objects.get(id = platoon)
        form.platoon = platoon
        if form.is_valid():
            usname = request.POST.get('name') + " " + request.POST.get('second_name')
            if User.objects.filter(username = usname).exists():
                user = User.objects.get(username = usname)
            else:
                user = form.save(commit = False)
                user.username = usname
                user = form.save()
            authenticate(user)
            login(request, user)
            return redirect('/cyberpolygon/')
    else:
        form = SignUpForm()
    return render(request, 'registration/reg_user.html', {'form': form})
