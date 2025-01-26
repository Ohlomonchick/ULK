from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from interface.models import (
    Competition, Lab, Answers, User
    # plus any other models you need, e.g. Platoon, LabLevel, etc.
)


class CompetitionDetailViewTest(TestCase):
    def setUp(self):
        # 1) Create a user
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass"
        )

        # 2) Create a Lab with some known answer_flag
        self.lab = Lab.objects.create(
            name="Test Lab",
            platform="NO",
            answer_flag="CORRECT_FLAG"
        )

        # 3) Create a Competition object
        self.competition = Competition.objects.create(
            slug="test-competition-detail",
            lab=self.lab,
            start=timezone.now() - timedelta(hours=1),   # started 1 hour ago
            finish=timezone.now() + timedelta(hours=1),  # finishes in 1 hour
            participants=1  # just a placeholder, not strictly required
        )

    def test_competition_detail_view(self):
        """
        1. "available" while the user has not answered yet.
        2. "submitted" if user's answer_flag is correct.
        3. "submitted" (and not "available") if an answer record already exists in DB.
        """

        # Log in so we have self.request.user in the view
        self.client.login(username="testuser", password="testpass")

        # -----------------------------------------------------------------
        # PART 1: No answer_flag => user hasn't answered => "available" = True
        # -----------------------------------------------------------------
        detail_url = reverse("interface:competition-detail", kwargs={"slug": self.competition.slug})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)

        # The view checks if there's an existing Answers record for this user.
        # Because we have none, we expect 'submitted' = False and 'available' = True (since finish > now)
        self.assertIn("submitted", response.context, "Context should have 'submitted' key.")
        self.assertFalse(response.context["submitted"], "Expected 'submitted' = False when user has no answers.")

        self.assertIn("available", response.context, "Context should have 'available' key when user has no answer.")
        self.assertTrue(response.context["available"], "Expected 'available' = True if no existing answers and still before finish.")

        # -----------------------------------------------------------------
        # PART 2: Provide correct answer_flag => should create an Answers record => "submitted" = True
        # -----------------------------------------------------------------
        # We'll call the same view but with query param answer_flag = "CORRECT_FLAG"
        response2 = self.client.get(detail_url, {"answer_flag": "CORRECT_FLAG"})
        self.assertEqual(response2.status_code, 200)

        # After a correct answer, the view sets context["submitted"] = True and inserts an Answers record.
        # Let's confirm it in the DB:
        answer_exists = Answers.objects.filter(user=self.user, lab=self.lab).exists()
        self.assertTrue(answer_exists, "An Answers object should have been created for the correct flag.")

        # Check context:
        self.assertIn("submitted", response2.context)
        self.assertTrue(response2.context["submitted"], "Expected 'submitted' = True after correct flag submission.")

        self.assertFalse(response2.context["available"], "Once user has answered, 'available' should not appear in context.")

        # -----------------------------------------------------------------
        # PART 3: If an Answers record already exists (simulate it was created externally),
        # the view should show 'submitted' and not 'available'.
        # -----------------------------------------------------------------
        # We'll manually delete the existing answer and re-add it to simulate a fresh scenario.
        Answers.objects.filter(user=self.user, lab=self.lab).delete()
        # Create a new answer object *before* the user visits the page
        Answers.objects.create(user=self.user, lab=self.lab, datetime=timezone.now())

        # Now visit the detail page again
        response3 = self.client.get(detail_url)
        self.assertEqual(response3.status_code, 200)

        # Because an existing Answers record is found, we expect "submitted"=True
        self.assertTrue(response3.context["submitted"], "Expected 'submitted' = True if user already has an Answers record.")

        # And again, 'available' should not appear (the code only sets 'available' = True if answers is None)
        self.assertFalse(response3.context["available"], "Expected 'available= False' if user already submitted.")
