from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
from datetime import timedelta

from interface.forms import CompetitionForm
from interface.models import (
    Competition, Platoon, User, Lab, LabLevel, LabTask, IssuedLabs
)


class CompetitionFormTest(TestCase):
    def setUp(self):
        # Create a Lab that uses "PN" platform to trigger external calls
        self.lab = Lab.objects.create(
            name="PN Lab",
            platform="PN"  # So it attempts to call pf_login/create_lab on save
        )

        # Create a LabLevel
        self.level = LabLevel.objects.create(
            lab=self.lab,
            level_number=1,
            description=""
        )

        # Create some tasks
        self.task1 = LabTask.objects.create(lab=self.lab, task_id="Task 1")
        self.task2 = LabTask.objects.create(lab=self.lab, task_id="Task 2")

        # Create a Platoon
        self.platoon = Platoon.objects.create(
            number=1
        )

        # Create some users in the platoon
        self.users_in_platoon = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"user_platoon_{i}",
                first_name=f"Platoon_{i}",
                last_name="User",
                password="testpass",
                platoon=self.platoon
            )
            self.users_in_platoon.append(user)

        # Create some users NOT in the platoon
        self.non_platoon_users = []
        for i in range(2):
            user = User.objects.create_user(
                username=f"user_nop_{i}",
                first_name=f"NoPlatoon_{i}",
                last_name="User",
                password="testpass",
                platoon=None
            )
            self.non_platoon_users.append(user)

        # Start/finish times in the future so validation passes
        self.start_time = timezone.now() + timedelta(hours=1)
        self.finish_time = timezone.now() + timedelta(hours=2)

    @patch("interface.models.delete_lab_with_session_destroy", return_value=None)
    @patch("interface.forms.logout", return_value=None)
    @patch("interface.forms.create_all_lab_nodes_and_connectors", return_value=None)
    @patch("interface.forms.create_lab", return_value=None)
    @patch("interface.forms.pf_login", return_value=("mock_cookie", "mock_xsrf"))
    @patch("interface.models.logout", return_value=None)
    @patch("interface.models.create_all_lab_nodes_and_connectors", return_value=None)
    @patch("interface.models.create_lab", return_value=None)
    @patch("interface.models.pf_login", return_value=("mock_cookie", "mock_xsrf"))
    def test_competition_form_creation_and_deletion(
        self,
        mock_pf_login_models,  # 8th decorator is 1st argument
        mock_create_lab_models,
        mock_create_nodes_models,
        mock_logout_models,
        mock_pf_login_forms,  # 4th decorator is 5th argument
        mock_create_lab_forms,
        mock_create_nodes_forms,
        mock_logout_forms,
        mock_delete_lab
    ):
        """
        1) Submit data through the CompetitionForm to create a Competition.
        2) Confirm IssuedLabs are created for platoon users and non-platoon users.
        3) Delete the Competition, verify IssuedLabs are removed.
        """

        # Prepare form data
        form_data = {
            "slug": "test-competition-form",
            "start": self.start_time,
            "finish": self.finish_time,
            "lab": self.lab.pk,        # Must reference primary key
            "level": self.level.pk,    # Same for foreign key fields
            "platoons": [self.platoon.pk],  # ManyToMany => list of IDs
            "non_platoon_users": [u.pk for u in self.non_platoon_users],
            "tasks": [self.task1.pk, self.task2.pk],
        }
        # Note: The CompetitionForm uses ModelForm fields `__all__`, 
        # so make sure to fill in any required fields.

        # Instantiate the form with data
        form = CompetitionForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        # Save the form
        competition = form.save()

        # Make sure external calls were triggered (optional check)
        mock_pf_login_models.assert_called()
        mock_create_lab_models.assert_called()
        mock_create_nodes_models.assert_called()
        mock_logout_models.assert_called()
        mock_pf_login_forms.assert_called()
        mock_create_lab_forms.assert_called()
        mock_create_nodes_forms.assert_called()
        mock_logout_forms.assert_called()

        # Verify that the competition is actually created in DB
        self.assertIsInstance(competition, Competition)
        self.assertTrue(Competition.objects.filter(pk=competition.pk).exists())

        # --- Verify IssuedLabs creation ---
        # Should be created for each platoon user + each non-platoon user
        for user in self.non_platoon_users:
            user_issued_in_competition = competition.issued_labs.filter(user=user)
            self.assertTrue(
                user_issued_in_competition.exists(),
                f"IssuedLabs not found for user {user.username} in this competition"
            )

        # More complex asserts on pnet calls
        self.assertEqual(
            mock_create_lab_forms.call_count,
            len(self.users_in_platoon),
            "Expected `create_lab` to be called once for each platoon user."
        )
        self.assertEqual(
            mock_create_nodes_forms.call_count,
            len(self.users_in_platoon),
            "Expected `create_all_lab_nodes_and_connectors` to be called once for each platoon user."
        )
        self.assertEqual(
            mock_create_lab_models.call_count,
            len(self.non_platoon_users),
            "Expected `create_lab` to be called once for each non-platoon user."
        )

        # Store all pks of IssuedLabs that belong to this competition
        competition_issued_labs_pks = list(competition.issued_labs.values_list('pk', flat=True))

        # Now delete the competition
        competition.delete()

        self.assertEqual(
            mock_delete_lab.call_count,
            len(self.non_platoon_users) + len(self.users_in_platoon),
            "Expected `delete_lab_with_session_destroy` to be called once for each user."
        )

        # Verify they are truly removed from the database
        for pk in competition_issued_labs_pks:
            self.assertFalse(
                IssuedLabs.objects.filter(pk=pk).exists(),
                f"IssuedLabs with pk={pk} should have been deleted after competition deletion."
            )
