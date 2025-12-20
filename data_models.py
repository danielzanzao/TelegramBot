"""
Data models and storage for EnactusBOT
"""

from datetime import datetime, time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

@dataclass
class WorkHour:
    """Data class for storing work hour information"""
    member_name: str
    task_type: str
    project_area: str
    date: str
    hours: float
    modality: str
    description: str
    status: str = "Pendente"  # Pendente, Aprovado, Reprovado
    approved_by: Optional[str] = None
    approval_date: Optional[datetime] = None
    telegram_user_id: int = 0
    ho_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class ReminderFrequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class ReminderType(Enum):
    HO = "ho"
    PCH = "pch"

@dataclass
class Reminder:
    """Data class for storing reminder information"""
    user_id: int
    member_name: str
    type: ReminderType
    frequency: ReminderFrequency
    time_of_day: time  # Time to send reminder
    day_of_week: Optional[int] = None # 0-6 (Mon-Sun)
    day_of_month: Optional[int] = None # 1-31
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_sent: Optional[datetime] = None

@dataclass
class Manager:
    """Data class for storing manager information"""
    telegram_user_id: int
    name: str
    managed_scopes: List[str]  # Areas or projects they manage
    is_active: bool = True

class DataStorage:
    """In-memory data storage for the MVP"""
    
    def __init__(self):
        self.work_hours: List[WorkHour] = []
        self.user_sessions: Dict[int, Dict] = {}
        self.reminders: List[Reminder] = []
        self.managers: List[Manager] = []
    
    def add_work_hour(self, work_hour: WorkHour):
        """Add a work hour record"""
        self.work_hours.append(work_hour)
    
    def get_user_session(self, user_id: int) -> Dict:
        """Get or create user session"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        return self.user_sessions[user_id]
    
    def clear_user_session(self, user_id: int):
        """Clear user session data"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
    
    
    # Reminder management methods
    def set_persistence_callback(self, callback):
        """Set callback for saving reminders"""
        self.save_reminders_callback = callback

    def add_reminder(self, reminder: Reminder):
        """Add or update a reminder"""
        # Remove existing reminder of same type for the user
        self.reminders = [r for r in self.reminders 
                         if not (r.user_id == reminder.user_id and r.type == reminder.type)]
        self.reminders.append(reminder)
        
        if hasattr(self, 'save_reminders_callback') and self.save_reminders_callback:
            try:
                self.save_reminders_callback(self.reminders)
            except Exception as e:
                print(f"Error auto-saving reminders: {e}")
    
    def get_user_reminders(self, user_id: int) -> List[Reminder]:
        """Get all reminders for a user"""
        return [r for r in self.reminders if r.user_id == user_id]
        
    def get_user_reminder_by_type(self, user_id: int, r_type: ReminderType) -> Optional[Reminder]:
        """Get specific reminder for a user"""
        for r in self.reminders:
            if r.user_id == user_id and r.type == r_type:
                return r
        return None
    
    def remove_user_reminder(self, user_id: int, r_type: ReminderType):
        """Remove specific reminder"""
        prev_len = len(self.reminders)
        self.reminders = [r for r in self.reminders 
                         if not (r.user_id == user_id and r.type == r_type)]
        
        if len(self.reminders) < prev_len and hasattr(self, 'save_reminders_callback') and self.save_reminders_callback:
             try:
                self.save_reminders_callback(self.reminders)
             except Exception as e:
                print(f"Error auto-saving reminders: {e}")
    
    def get_active_reminders(self) -> List[Reminder]:
        """Get all active reminders"""
        return [r for r in self.reminders if r.is_active]
    
    def update_reminder_last_sent(self, user_id: int, r_type: ReminderType, sent_time: datetime):
        """Update when reminder was last sent"""
        changed = False
        for reminder in self.reminders:
            if reminder.user_id == user_id and reminder.type == r_type:
                reminder.last_sent = sent_time
                changed = True
                break
        
        # We don't necessarily need to save to cloud on every "last_sent" update as it might be too frequent/unnecessary load
        # But if we wanted perfect state recovery, we would. For now, let's skip to save API calls.
        # If the user restarts the bot, 'last_sent' being lost means they *might* get a duplicate reminder if within the same minute,
        # but the scheduler logic usually handles this by checking current time.
    
    # ... (Manager methods remain unchanged) ...
    def add_manager(self, manager: Manager):
        """Add a manager"""
        # Remove existing manager for same user if exists
        self.managers = [m for m in self.managers if m.telegram_user_id != manager.telegram_user_id]
        self.managers.append(manager)
    
    def get_manager_by_user_id(self, user_id: int) -> Optional[Manager]:
        """Get manager by telegram user ID"""
        for manager in self.managers:
            if manager.telegram_user_id == user_id and manager.is_active:
                return manager
        return None
    
    def get_manager_for_area(self, area_or_project: str) -> Optional[Manager]:
        """Get manager responsible for a specific area or project"""
        for manager in self.managers:
            if manager.is_active and area_or_project in manager.managed_areas:
                return manager
        return None
    
    def get_pending_work_hours_for_manager(self, manager: Manager) -> List[WorkHour]:
        """Get all pending work hours for a specific manager"""
        pending_hours = []
        for work_hour in self.work_hours:
            if (work_hour.status == "Pendente" and 
                work_hour.project_area in manager.managed_areas):
                pending_hours.append(work_hour)
        return pending_hours
    
    def update_work_hour_status(self, ho_id: str, status: str, approved_by: str, approval_date: datetime):
        """Update work hour approval status"""
        for work_hour in self.work_hours:
            if work_hour.ho_id == ho_id:
                work_hour.status = status
                work_hour.approved_by = approved_by
                work_hour.approval_date = approval_date
                break

@dataclass
class MemberProfile:
    name: str
    telegram_id: Optional[int] = None
    roles: List[str] = field(default_factory=list)
    managed_scopes: List[str] = field(default_factory=list)

class BotData:
    """Static data for the bot"""
    
    # Default members (fallback/migration source)
    DEFAULT_MEMBERS = [
        MemberProfile("Adriana Miguel Santos"),
        MemberProfile("Amanda Sousa Santos"),
        MemberProfile("Ana Beatriz Costa Sá Peixoto"),
        MemberProfile("Ana Cristiane da Silva Pereira Ribeiro"),
        MemberProfile("Ana Luiza de Souza Lopes"),
        MemberProfile("Augusto Celso Batista Franklim"),
        MemberProfile("Bernardo Ribeiro Leal"),
        MemberProfile("Bruna Jobim Villar"),
        MemberProfile("Bruno Lage Correia"),
        MemberProfile("Caique Ribeiro de Araujo"),
        MemberProfile("Camyla Mabisis Araújo"),
        MemberProfile("Daniel da Silva Mendes", telegram_id=6229013307, roles=["QLD","Odoyá"], managed_scopes=["QLD"]),
        MemberProfile("Dayanne Aranha Honorio"),
        MemberProfile("Emily Thaise Sousa da Silva"),
        MemberProfile("Fábia Wendy"),
        MemberProfile("Fernanda Luizi Garcia de Souza"),
        MemberProfile("Gabriel Dias da Rocha"),
        MemberProfile("Gabriel Silva dos Santos"),
        MemberProfile("Geisa Kelly de Oliveira Machado"),
        MemberProfile("Geovanna Rosa Fernandes"),
        MemberProfile("Gilmar Pinheiro Fernandes Júnior"),
        MemberProfile("Giovanna de Souza e Mello Baggio Meliante"),
        MemberProfile("Graziela Miranda Bellizzi"),
        MemberProfile("Henrique de Carvalho Liebert"),
        MemberProfile("Isabela dos Santos Mattoso"),
        MemberProfile("Jhennifer de Oliveira Ribeiro"),
        MemberProfile("João Pedro dos Santos Heleno"),
        MemberProfile("Jonathan André de Andrade Neves"),
        MemberProfile("José Lucas Ferreira Pereira"),
        MemberProfile("Julia Neves Costa Sa"),
        MemberProfile("Laís de Souza Trindade"),
        MemberProfile("Laiza Florencio de Souza Nascimento"),
        MemberProfile("Laryssa de Andrade Alves"),
        MemberProfile("Lucas de Freitas Gonçalves"),
        MemberProfile("Maria Eduarda Oliveira de Lima"),
        MemberProfile("Maria Heloísa Rangel da Silva"),
        MemberProfile("Maria Luiza Arruda Rezende"),
        MemberProfile("Maria Paula Ferreira Santos Carvalho"),
        MemberProfile("Mariana Fernandes Pinheiro"),
        MemberProfile("Mariana Solon Ribeiro Sanches"),
        MemberProfile("Pedro da Silva Ferreira"),
        MemberProfile("Peter Lemos Dos Passos"),
        MemberProfile("Peterson Guimarães do Nascimento"),
        MemberProfile("Renato Miranda de Almeida Neto"),
        MemberProfile("Rosângela Vieira de Souza"),
        MemberProfile("Sophia Cristina Santos da Silva"),
        MemberProfile("Stela Almeida Silveira"),
        MemberProfile("Thayná Araujo de Oliveira"),
        MemberProfile("Walter Veridiano dos Santos")
    ]
    
    # Current active members list
    MEMBERS_DB = list(DEFAULT_MEMBERS)
    
    @classmethod
    def set_members(cls, members: List[MemberProfile]):
        """Update the members list from external source"""
        cls.MEMBERS_DB = members
        # Update flat list compatibility
        cls.MEMBERS = cls.get_member_names()

    @classmethod
    def get_member_names(cls) -> List[str]:
        """Returns list of member names for backward compatibility"""
        return [m.name for m in cls.MEMBERS_DB]
    
    # Compatibility property
    @property
    def MEMBERS(self):
         return self.get_member_names()
         
    # Make MEMBERS accessible as class attribute too for existing code
    MEMBERS = [m.name for m in MEMBERS_DB]

    @classmethod
    def get_member(cls, telegram_id: int) -> Optional[MemberProfile]:
        for member in cls.MEMBERS_DB:
            if member.telegram_id == telegram_id:
                return member
        return None

    @classmethod
    def is_user_in_role(cls, telegram_id: int, role: str) -> bool:
        member = cls.get_member(telegram_id)
        if member and role in member.roles:
            return True
        return False
        
    @classmethod
    def get_user_role(cls, telegram_id: int) -> List[str]:
         member = cls.get_member(telegram_id)
         if member:
             return member.roles
         return []

    @classmethod
    def get_managed_scopes(cls, telegram_id: int) -> List[str]:
        """Get list of scopes (areas/projects) managed by a user"""
        member = cls.get_member(telegram_id)
        if member:
            return member.managed_scopes
        return []

    # Projetos da Enactus
    PROJECTS = ["Odoyá", "Maná"]
    
    # Áreas da Enactus
    AREAS = ["DAF", "GP", "MKT", "QLD", "PSD"]
    
    # Modalidades de trabalho
    MODALITIES = ["Presencial", "EAD"]
    
    # Links (você deve atualizar com os links reais)
    CENTRAL_ENACTUS_LINK = "https://drive.google.com/drive/folders/1pFo4CP_LVCaI2hdQQyyKVr4IQfXTH204"
    CLIMATE_SURVEY_LINK = "https://forms.google.com/"
    
    # Status de aprovação possíveis
    APPROVAL_STATUS = ["Pendente", "Aprovada", "Reprovada"]
    
    # ====== CONFIGURAÇÃO DE GERENTES ======
    # Deprecated in favor of MemberProfile.managed_scopes, keeping for safety
    DEFAULT_MANAGERS = [
        (6229013307, "Daniel da Silva Mendes", ["QLD","Maná"]),
    ]

# Global storage instance
storage = DataStorage()
