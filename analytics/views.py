from datetime import timedelta
from django.db.models.functions import TruncDate
from django.db.models import Count, F, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanViewAnalytics
from paginations.pagination import AnalyticsEventPagination
from blog.models import Post

from .models import AnalyticsEvent
from .serializers import AnalyticsEventSerializer


# =========================
# ANALYTICS LIST VIEW
# =========================
class AnalyticsEventListView(APIView):
    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get(self, request, *args, **kwargs):
        events = AnalyticsEvent.objects.select_related(
            "actor",
            "post",
        ).all()

        event_type = request.query_params.get("type")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        # Filter by event type
        if event_type:
            valid_types = {
                value
                for value, _label in AnalyticsEvent.EventType.choices
            }

            if event_type not in valid_types:
                return Response(
                    {"error": "Invalid event type."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            events = events.filter(event_type=event_type)

        # Initialize parsed dates to avoid referencing
        # variables that may not have been assigned.
        parsed_start = None
        parsed_end = None

        # Validate start date
        if start_date:
            parsed_start = parse_date(start_date)

            if parsed_start is None:
                return Response(
                    {
                        "error": (
                            "Invalid start_date. "
                            "Use YYYY-MM-DD."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate end date
        if end_date:
            parsed_end = parse_date(end_date)

            if parsed_end is None:
                return Response(
                    {
                        "error": (
                            "Invalid end_date. "
                            "Use YYYY-MM-DD."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Ensure the start date is not later than the end date
        if (
            parsed_start is not None
            and parsed_end is not None
            and parsed_start > parsed_end
        ):
            return Response(
                {
                    "error": (
                        "start_date cannot be after end_date."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Apply date filters only after validation succeeds
        if parsed_start is not None:
            events = events.filter(
                occurred_at__date__gte=parsed_start
            )

        if parsed_end is not None:
            events = events.filter(
                occurred_at__date__lte=parsed_end
            )

        # Paginate the results
        paginator = AnalyticsEventPagination()

        page = paginator.paginate_queryset(
            events,
            request,
            view=self,
        )

        serializer = AnalyticsEventSerializer(
            page,
            many=True,
        )

        return paginator.get_paginated_response(
            serializer.data
        )
    
# =========================
# ANALYTICS SUMMARY VIEW
# =========================
class AnalyticsSummaryView(APIView):
    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get(self, request,*args,**kwargs):
        events = AnalyticsEvent.objects.all()

        today = timezone.localdate()
        today_events = events.filter(occurred_at__date=today)

        event_counts = {
            item["event_type"]: item["total"]
            for item in events.values("event_type").annotate(
                total=Count("id")
            )
        }
        activity_breakdown = [
            {
                "event_type": item["event_type"],
                "total": item["total"],
            }
            for item in events.values("event_type").annotate(
                total=Count("id")
            ).order_by("-total")
        ]

        return Response(
            {
                "total_events": events.count(),
                "events_today": today_events.count(),
                "post_views": event_counts.get("post_view", 0),
                "reactions": event_counts.get("reaction", 0),
                "comments": event_counts.get("comment", 0),
                "shares": event_counts.get("share", 0),
                "bookmarks": event_counts.get("bookmark", 0),
                "follows": event_counts.get("follow", 0),
                "post_publications": event_counts.get(
                    "post_published", 0
                ),
                "activity_breakdown": activity_breakdown,
            },
            status=status.HTTP_200_OK,
        )

# =========================
# TOP VIEWED POST VIEW
# =========================

class TopViewedPostsView(APIView):
    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get(self, request, *args, **kwargs):
        posts = (
            AnalyticsEvent.objects
            .filter(
                event_type=AnalyticsEvent.EventType.POST_VIEW,
                post__isnull=False,
            )
            .values(
                "post_id",
                "post__title",
                "post__slug",
            )
            .annotate(
                total_views=Count("id"),
            )
            .order_by("-total_views", "post__title")[:10]
        )

        return Response(
            {
                "count": len(posts),
                "results": [
                    {
                        "post_id": item["post_id"],
                        "title": item["post__title"],
                        "slug": item["post__slug"],
                        "total_views": item["total_views"],
                    }
                    for item in posts
                ],
            },
            status=status.HTTP_200_OK,
        )

# =========================
# TOP ENGAGED POST VIEW
# =========================
class TopEngagedPostsView(APIView):
    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get(self, request, *args, **kwargs):
        engagement_types = [
            AnalyticsEvent.EventType.REACTION,
            AnalyticsEvent.EventType.COMMENT,
            AnalyticsEvent.EventType.SHARE,
            AnalyticsEvent.EventType.BOOKMARK,
        ]

        posts = (
            AnalyticsEvent.objects
            .filter(
                event_type__in=engagement_types,
                post__isnull=False,
            )
            .values(
                "post_id",
                "post__title",
                "post__slug",
            )
            .annotate(
                total_engagements=Count("id"),
            )
            .order_by("-total_engagements", "post__title")[:10]
        )

        return Response(
            {
                "count": len(posts),
                "results": [
                    {
                        "post_id": item["post_id"],
                        "title": item["post__title"],
                        "slug": item["post__slug"],
                        "total_engagements": item[
                            "total_engagements"
                        ],
                    }
                    for item in posts
                ],
            },
            status=status.HTTP_200_OK,
        )

# =========================
# TRAFFIC TRENDS VIEW
# =========================

class TrafficTrendsView(APIView):
    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get(self, request, *args, **kwargs):
        start_date_value = request.query_params.get("start_date")
        end_date_value = request.query_params.get("end_date")

        today = timezone.localdate()
        default_start_date = today - timedelta(days=6)

        start_date = default_start_date
        end_date = today

        if start_date_value:
            start_date = parse_date(start_date_value)
            if start_date is None:
                return Response(
                    {
                        "error": (
                            "Invalid start_date. "
                            "Use YYYY-MM-DD."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_value:
            end_date = parse_date(end_date_value)
            if end_date is None:
                return Response(
                    {
                        "error": (
                            "Invalid end_date. "
                            "Use YYYY-MM-DD."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if start_date > end_date:
            return Response(
                {
                    "error": (
                        "start_date cannot be after end_date."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        date_range_days = (end_date - start_date).days

        if date_range_days > 365:
            return Response(
                {
                    "error": (
                        "Date range cannot exceed 366 calendar days."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        events = AnalyticsEvent.objects.filter(
            occurred_at__date__gte=start_date,
            occurred_at__date__lte=end_date,
        )

        daily_events = (
            events
            .annotate(day=TruncDate("occurred_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )

        daily_views = (
            events
            .filter(
                event_type=AnalyticsEvent.EventType.POST_VIEW
            )
            .annotate(day=TruncDate("occurred_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )

        engagement_types = [
            AnalyticsEvent.EventType.REACTION,
            AnalyticsEvent.EventType.COMMENT,
            AnalyticsEvent.EventType.SHARE,
            AnalyticsEvent.EventType.BOOKMARK,
        ]

        daily_engagements = (
            events
            .filter(event_type__in=engagement_types)
            .annotate(day=TruncDate("occurred_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )

        totals_by_day = {
            item["day"]: item["total"]
            for item in daily_events
        }

        views_by_day = {
            item["day"]: item["total"]
            for item in daily_views
        }

        engagements_by_day = {
            item["day"]: item["total"]
            for item in daily_engagements
        }

        results = []

        for offset in range(date_range_days + 1):
            current_day = start_date + timedelta(days=offset)

            results.append(
                {
                    "date": current_day.isoformat(),
                    "total_events": totals_by_day.get(
                        current_day, 0
                    ),
                    "post_views": views_by_day.get(
                        current_day, 0
                    ),
                    "engagements": engagements_by_day.get(
                        current_day, 0
                    ),
                }
            )

        return Response(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": len(results),
                "results": results,
            },
            status=status.HTTP_200_OK,
        )

# =========================
# TRENDING POSTS VIEW
# =========================

class TrendingPostsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        days_value = request.query_params.get("days", "7")

        try:
            days = int(days_value)
        except (TypeError, ValueError):
            return Response(
                {"error": "days must be an integer between 1 and 30."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not 1 <= days <= 30:
            return Response(
                {"error": "days must be between 1 and 30."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cutoff = timezone.now() - timedelta(days=days)

        recent_events = Q(
            analytics_events__occurred_at__gte=cutoff
        )

        posts = (
            Post.objects
            .filter(
                status="published",
                visibility="public",
            )
            .annotate(
                recent_views=Count(
                    "analytics_events",
                    filter=(
                        recent_events
                        & Q(
                            analytics_events__event_type=(
                                AnalyticsEvent.EventType.POST_VIEW
                            )
                        )
                    ),
                    distinct=True,
                ),
                recent_reactions=Count(
                    "analytics_events",
                    filter=(
                        recent_events
                        & Q(
                            analytics_events__event_type=(
                                AnalyticsEvent.EventType.REACTION
                            )
                        )
                    ),
                    distinct=True,
                ),
                recent_comments=Count(
                    "analytics_events",
                    filter=(
                        recent_events
                        & Q(
                            analytics_events__event_type=(
                                AnalyticsEvent.EventType.COMMENT
                            )
                        )
                    ),
                    distinct=True,
                ),
                recent_shares=Count(
                    "analytics_events",
                    filter=(
                        recent_events
                        & Q(
                            analytics_events__event_type=(
                                AnalyticsEvent.EventType.SHARE
                            )
                        )
                    ),
                    distinct=True,
                ),
                recent_bookmarks=Count(
                    "analytics_events",
                    filter=(
                        recent_events
                        & Q(
                            analytics_events__event_type=(
                                AnalyticsEvent.EventType.BOOKMARK
                            )
                        )
                    ),
                    distinct=True,
                ),
            )
            .annotate(
                trending_score=(
                    F("recent_views")
                    + F("recent_reactions") * 3
                    + F("recent_comments") * 4
                    + F("recent_shares") * 3
                    + F("recent_bookmarks") * 2
                )
            )
            .filter(trending_score__gt=0)
            .select_related("author", "category")
            .order_by("-trending_score", "-published_at")[:10]
        )

        results = [
            {
                "id": str(post.id),
                "title": post.title,
                "slug": post.slug,
                "excerpt": post.excerpt,
                "featured_image": post.featured_image,
                "author": post.author.username,
                "category": post.category.name if post.category else None,
                "published_at": post.published_at,
                "recent_views": post.recent_views,
                "recent_reactions": post.recent_reactions,
                "recent_comments": post.recent_comments,
                "recent_shares": post.recent_shares,
                "recent_bookmarks": post.recent_bookmarks,
                "trending_score": post.trending_score,
            }
            for post in posts
        ]

        return Response(
            {
                "period_days": days,
                "count": len(results),
                "results": results,
            },
            status=status.HTTP_200_OK,
        )