"""
FSM States — GitroHub v2.0
All finite state machine states stored in Redis via aiogram FSM.
"""
from aiogram.fsm.state import State, StatesGroup


class AuthFlow(StatesGroup):
    awaiting_oauth = State()


class RepoFlow(StatesGroup):
    creating_name = State()
    creating_visibility = State()
    creating_readme = State()
    creating_gitignore = State()
    creating_license = State()
    creating_description = State()
    deleting_step1 = State()       # type repo name
    deleting_step2 = State()       # email OTP
    deleting_step3 = State()       # mobile approval
    renaming = State()
    transferring = State()
    setting_topics = State()
    setting_description = State()
    setting_website = State()


class FileFlow(StatesGroup):
    creating_name = State()
    creating_content = State()
    editing = State()              # awaiting edited file back
    moving_destination = State()
    renaming = State()
    searching = State()


class CommitFlow(StatesGroup):
    awaiting_file = State()           # single file — waiting for upload
    awaiting_path = State()           # declare path before upload
    batch_collecting = State()        # collecting files one by one
    awaiting_zip = State()            # waiting for ZIP file
    awaiting_message = State()        # write commit message
    confirming_sensitive = State()    # .env / secrets warning
    batch_paths_done = State()        # paths declared, ready for files


class BranchFlow(StatesGroup):
    creating = State()
    renaming = State()
    comparing = State()               # type two branch names


class PullFlow(StatesGroup):
    creating_title = State()
    creating_body = State()


class IssueFlow(StatesGroup):
    creating_title = State()
    creating_body = State()
    commenting = State()


class ReleaseFlow(StatesGroup):
    creating_tag = State()
    creating_title = State()
    creating_notes = State()


class ProfileFlow(StatesGroup):
    editing_name = State()
    editing_bio = State()
    editing_company = State()
    editing_location = State()
    editing_website = State()
    editing_twitter = State()
    editing_link = State()          # adding a social link
    editing_pronouns = State()
    editing_learning = State()


class SettingsFlow(StatesGroup):
    editing_timezone = State()
    editing_pm_message = State()    # private message full text
    editing_pm_owner = State()
    editing_pm_link = State()
    adding_alias_shortcut = State()
    adding_alias_command = State()
    adding_template = State()
    adding_savedpath = State()
    setting_quiet_from = State()
    setting_quiet_until = State()


class ExploreFlow(StatesGroup):
    searching = State()
    downloading = State()           # paste URL
    finding_user = State()


class ProjectFlow(StatesGroup):
    creating_name = State()
    creating_description = State()
    adding_file_name = State()
    adding_file_content = State()


class InviteFlow(StatesGroup):
    creating = State()


class GistFlow(StatesGroup):
    creating_filename = State()
    creating_content = State()
    creating_description = State()
