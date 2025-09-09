"""
Data models and storage for EnactusBOT
"""

from datetime import datetime, time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

class ReminderFrequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

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

@dataclass
class Reminder:
    """Data class for storing reminder information"""
    user_id: int
    member_name: str
    frequency: ReminderFrequency
    time_of_day: time  # Time to send reminder (e.g., 18:00)
    is_active: bool
    created_at: datetime
    last_sent: Optional[datetime] = None

@dataclass
class Manager:
    """Data class for storing manager information"""
    telegram_user_id: int
    name: str
    managed_areas: List[str]  # Areas or projects they manage
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
    def add_reminder(self, reminder: Reminder):
        """Add a reminder"""
        # Remove existing reminder for same user if exists
        self.reminders = [r for r in self.reminders if r.user_id != reminder.user_id]
        self.reminders.append(reminder)
    
    def get_user_reminder(self, user_id: int) -> Optional[Reminder]:
        """Get user's reminder"""
        for reminder in self.reminders:
            if reminder.user_id == user_id:
                return reminder
        return None
    
    def remove_user_reminder(self, user_id: int):
        """Remove user's reminder"""
        self.reminders = [r for r in self.reminders if r.user_id != user_id]
    
    def get_active_reminders(self) -> List[Reminder]:
        """Get all active reminders"""
        return [r for r in self.reminders if r.is_active]
    
    def update_reminder_last_sent(self, user_id: int, sent_time: datetime):
        """Update when reminder was last sent"""
        for reminder in self.reminders:
            if reminder.user_id == user_id:
                reminder.last_sent = sent_time
                break
    
    # Manager management methods
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

class BotData:
    """Static data for the bot"""
    
    # Lista de membros da Enactus - em ordem alfabética
    MEMBERS = [
        "Ana Lívia Pinheiro dos Santos",
        "Augusto Celso Batista Franklim",
        "Bernardo Ribeiro Leal",
        "Bruna Jobim Villar",
        "Bruno Lage Correia",
        "Camyla Mabisis Araújo",
        "Daniel da Silva Mendes",
        "Davi Chu de Oliveira",
        "Emily Thaise Sousa da Silva",
        "Fernanda Luizi Garcia de Souza",
        "Gabriel de Almeida Henrique",
        "Gabriel Dias da Rocha",
        "Gabriela Maia Felipe da Silva",
        "Geovanna Rosa Fernandes",
        "Gilmar Pinheiro Fernandes Júnior",
        "Giovanna de Souza e Mello Baggio Meliante",
        "Guilherme Damião Galdeano Nascimento",
        "Isabela dos Santos Mattoso",
        "Jhennifer de Oliveira Ribeiro",
        "João Pedro dos Santos Heleno",
        "Jonathan André de Andrade Neves",
        "Julia Neves Costa Sa",
        "Laís de Souza Trindade",
        "Laryssa de Andrade Alves",
        "Lavinya Martins de Lima",
        "Lucas de Freitas Gonçalves",
        "Maria Eduarda Oliveira de Lima",
        "Maria Heloísa Rangel da Silva",
        "Maria Luiza Arruda Rezende",
        "Maria Paula Ferreira Santos Carvalho",
        "Mariana Solon Ribeiro Sanches",
        "Pedro da Silva Ferreira",
        "Peterson Guimarães do Nascimento",
        "Rony da Silva Souza",
        "Rosângela Vieira de Souza",
        "Thamyres Ranzeiro Campos",
        "Thayná Araujo de Oliveira"
    ]
    
    # Projetos da Enactus
    PROJECTS = ["Odoyá", "Maná", "Gelé"]
    
    # Áreas da Enactus
    AREAS = ["DAF", "GP", "MKT", "QLD", "PSD"]
    
    # Modalidades de trabalho
    MODALITIES = ["Presencial", "EAD"]
    
    # Links (você deve atualizar com os links reais)
    CENTRAL_ENACTUS_LINK = "https://drive.google.com/drive/folders/1pFo4CP_LVCaI2hdQQyyKVr4IQfXTH204"
    CLIMATE_SURVEY_LINK = "https://forms.google.com/"
    
    # Status de aprovação possíveis
    APPROVAL_STATUS = ["Pendente", "Aprovado", "Reprovado"]
    
    # ====== CONFIGURAÇÃO DE GERENTES ======
    # Aqui você pode definir quais usuários são gerentes e quais áreas/projetos eles gerenciam
    # Format: (telegram_user_id, nome, [áreas/projetos_gerenciados])
    DEFAULT_MANAGERS = [
        # Exemplo de como configurar gerentes:
        # (123456789, "João Silva", ["DAF", "GP"]),      # Gerente de DAF e GP
        # (987654321, "Maria Santos", ["Odoyá"]),        # Gerente do projeto Odoyá
        # (555666777, "Pedro Costa", ["MKT", "QLD"]),    # Gerente de MKT e QLD
        (6229013307, "Daniel da Silva Mendes",["QLD","Maná"]),
        # SUBSTITUA PELOS GERENTES REAIS:
        # Para descobrir o telegram_user_id, peça para o gerente enviar /start no bot
        # e verificar nos logs ou implementar um comando /get_my_id
    ]

# Global storage instance
storage = DataStorage()
