from django.core.management.base import BaseCommand

from schoolprograms.demo_seed import seed_schoolprograms_demo


class Command(BaseCommand):
    help = "Seed realistic demo marketplace data for schoolprograms"

    def handle(self, *args, **options):
        summary = seed_schoolprograms_demo()
        self.stdout.write(
            self.style.SUCCESS(
                "seed_schoolprograms_demo completed "
                f"(providers={summary['providers']}, "
                f"approved_listings={summary['approved_listings']}, "
                f"pending_listings={summary['pending_listings']}, "
                f"draft_listings={summary['draft_listings']}, "
                f"published_reviews={summary['published_reviews']}, "
                f"threads={summary['threads']})"
            )
        )
