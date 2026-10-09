
from django.urls import path

from .views import (
    AnalyticsEventListView,
    AnalyticsSummaryView,
    TopViewedPostsView,
    TopEngagedPostsView,
    TrafficTrendsView,
    TrendingPostsView
)


urlpatterns = [
    path("events/",AnalyticsEventListView.as_view(),name="analytics-events"),
    path("summary/",AnalyticsSummaryView.as_view(),name="analytics-summary"),
    path("posts/top-viewed/",TopViewedPostsView.as_view(),name="analytics-top-viewed-posts"),
    path("posts/top-engaged/",TopEngagedPostsView.as_view(),name="analytics-top-engaged-posts"),
    path("traffic-trends/",TrafficTrendsView.as_view(),name="analytics-traffic-trends"),
    path("trending/",TrendingPostsView.as_view(),name="analytics-trending-posts",),
]