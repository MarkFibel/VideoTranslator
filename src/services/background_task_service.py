import asyncio
import logging
from typing import Callable, Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
import uuid
from datetime import datetime

from .sse_service import sse_service

logger = logging.getLogger(__name__)


class BackgroundTask:
    """Represents a background task"""
    def __init__(self, task_id: str, client_id: str, task_type: str, task_func: Callable, *args, **kwargs):
        self.task_id = task_id
        self.client_id = client_id
        self.task_type = task_type
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
        self.created_at = datetime.now()
        self.status = "pending"
        self.result: Optional[Any] = None
        self.error: Optional[str] = None


class BackgroundTaskService:
    """Service for managing background tasks and sending SSE notifications"""
    
    def __init__(self, max_workers: int = 4):
        self.tasks: Dict[str, BackgroundTask] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"Background Task Service initialized with {max_workers} workers")

    async def submit_task(
        self,
        client_id: str,
        task_type: str,
        task_func: Callable,
        *args,
        task_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Submit a background task for execution
        
        Args:
            client_id: ID of the client that submitted the task
            task_type: Type/name of the task
            task_func: Function to execute
            *args: Arguments for the task function
            task_id: Optional task ID. If not provided, UUID will be generated
            **kwargs: Keyword arguments for the task function
            
        Returns:
            str: Task ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # Create task object
        task = BackgroundTask(task_id, client_id, task_type, task_func, *args, **kwargs)
        self.tasks[task_id] = task
        
        logger.info(f"Background task submitted: {task_id} ({task_type}) for client: {client_id}")
        
        # Send task started notification via SSE
        await sse_service.send_to_client(
            client_id,
            "task_started",
            {
                "task_id": task_id,
                "task_type": task_type,
                "status": "started",
                "timestamp": task.created_at.isoformat()
            }
        )
        
        # Start the task asynchronously
        asyncio.create_task(self._execute_task(task))
        
        return task_id

    async def _execute_task(self, task: BackgroundTask):
        """Execute a background task and handle notifications"""
        try:
            logger.info(f"Starting execution of task: {task.task_id}")
            task.status = "running"
            
            # Send running notification via SSE
            await sse_service.send_to_client(
                task.client_id,
                "task_progress",
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "status": "running",
                    "progress": 0,
                    "message": "Task execution started"
                }
            )
            
            # Execute the task in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            if asyncio.iscoroutinefunction(task.task_func):
                # If task function is async, run it directly with task_id as first argument
                result = await task.task_func(task.task_id, *task.args, **task.kwargs)
            else:
                # If task function is sync, run it in thread pool
                result = await loop.run_in_executor(
                    self.executor,
                    task.task_func,
                    task.task_id,
                    *task.args
                )
            
            task.result = result
            task.status = "completed"
            
            logger.info(f"Task completed successfully: {task.task_id}")
            
            # Send completion notification via SSE
            await sse_service.send_to_client(
                task.client_id,
                "task_completed",
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "status": "completed",
                    "result": result,
                    "completed_at": datetime.now().isoformat()
                }
            )
            
            # Clean up client ID mapping after task completion
            sse_service.unmap_client_id(task.client_id)
            logger.info(f"Cleaned up SSE client mapping for completed task: {task.task_id}")
            
        except Exception as e:
            logger.error(f"Task execution failed: {task.task_id} - {str(e)}", exc_info=True)
            
            task.status = "failed"
            task.error = str(e)
            
            # Send failure notification via SSE
            await sse_service.send_to_client(
                task.client_id,
                "task_failed",
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.now().isoformat()
                }
            )
            
            # Clean up client ID mapping after task failure
            sse_service.unmap_client_id(task.client_id)
            logger.info(f"Cleaned up SSE client mapping for failed task: {task.task_id}")

    async def send_progress_update(
        self,
        task_id: str,
        progress: int,
        message: str = ""
    ):
        """Send progress update for a task via SSE"""
        if task_id not in self.tasks:
            logger.warning(f"Attempt to send progress for non-existent task: {task_id}")
            return
        
        task = self.tasks[task_id]
        
        await sse_service.send_to_client(
            task.client_id,
            "task_progress",
            {
                "task_id": task_id,
                "task_type": task.task_type,
                "status": "running",
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        logger.debug(f"Progress update sent for task {task_id}: {progress}% - {message}")

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a specific task"""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return {
            "task_id": task.task_id,
            "client_id": task.client_id,
            "task_type": task.task_type,
            "status": task.status,
            "created_at": task.created_at.isoformat(),
            "result": task.result,
            "error": task.error
        }

    def get_client_tasks(self, client_id: str) -> list:
        """Get all tasks for a specific client"""
        client_tasks = []
        for task in self.tasks.values():
            if task.client_id == client_id:
                client_tasks.append(self.get_task_status(task.task_id))
        return client_tasks

    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks"""
        current_time = datetime.now()
        tasks_to_remove = []
        
        for task_id, task in self.tasks.items():
            if task.status in ["completed", "failed"]:
                age_hours = (current_time - task.created_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
            logger.info(f"Cleaned up old task: {task_id}")

    def get_stats(self) -> Dict:
        """Get background task service statistics"""
        stats = {
            "total_tasks": len(self.tasks),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0
        }
        
        for task in self.tasks.values():
            if task.status in stats:
                stats[task.status] += 1
        
        return stats


# Global background task service instance
background_task_service = BackgroundTaskService()