from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import Chat, Conversation, UserProfile

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('user', 'truncated_message', 'truncated_response', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('user__username', 'message', 'response')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    def truncated_message(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    truncated_message.short_description = 'Message'

    def truncated_response(self, obj):
        return obj.response[:50] + '...' if len(obj.response) > 50 else obj.response
    truncated_response.short_description = 'Response'

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('truncated_question', 'truncated_answer', 'formatted_timestamp')
    list_filter = ('timestamp',)
    search_fields = ('question', 'answer')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)

    def truncated_question(self, obj):
        return obj.question[:50] + '...' if len(obj.question) > 50 else obj.question
    truncated_question.short_description = 'Question'

    def truncated_answer(self, obj):
        return obj.answer[:50] + '...' if len(obj.answer) > 50 else obj.answer
    truncated_answer.short_description = 'Answer'

    def formatted_timestamp(self, obj):
        return obj.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    formatted_timestamp.short_description = 'Timestamp'

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('gender', 'location', 'age', 'is_profile_completed')

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_age', 
                   'get_location', 'get_gender', 'get_profile_status')
    list_filter = ('userprofile__gender', 'userprofile__is_profile_completed')
    search_fields = ('username', 'email', 'userprofile__location')

    def get_age(self, obj):
        try:
            return obj.userprofile.age
        except UserProfile.DoesNotExist:
            return '-'
    get_age.short_description = 'Age'
    
    def get_location(self, obj):
        try:
            return obj.userprofile.location
        except UserProfile.DoesNotExist:
            return '-'
    get_location.short_description = 'Location'
    
    def get_gender(self, obj):
        try:
            return obj.userprofile.get_gender_display()
        except UserProfile.DoesNotExist:
            return '-'
    get_gender.short_description = 'Gender'

    def get_profile_status(self, obj):
        try:
            status = obj.userprofile.is_profile_completed
            if status:
                return format_html('<span style="color: green;">✓ Complete</span>')
            return format_html('<span style="color: red;">✗ Incomplete</span>')
        except UserProfile.DoesNotExist:
            return format_html('<span style="color: gray;">- No Profile -</span>')
    get_profile_status.short_description = 'Profile Status'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'age', 'location', 'gender', 'profile_status')
    list_filter = ('gender', 'is_profile_completed')
    search_fields = ('user__username', 'location')
    ordering = ('user__username',)

    def profile_status(self, obj):
        if obj.is_profile_completed:
            return format_html('<span style="color: green;">✓ Complete</span>')
        return format_html('<span style="color: red;">✗ Incomplete</span>')
    profile_status.short_description = 'Profile Status'
