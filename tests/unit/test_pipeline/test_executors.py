"""
Tests for pipeline executors.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestLocalExecutor:
    """Tests for LocalExecutor."""

    def test_executor_imports(self):
        """Test that the executor can be imported."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor, create_local_executor
        assert LocalExecutor is not None
        assert create_local_executor is not None

    def test_create_executor(self):
        """Test creating an executor."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        
        executor = LocalExecutor()
        assert executor is not None
        assert executor.stop_on_failure is True

    def test_create_executor_with_options(self):
        """Test creating an executor with options."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        import logging
        
        logger = logging.getLogger("test")
        executor = LocalExecutor(logger=logger, stop_on_failure=False)
        
        assert executor.logger is logger
        assert executor.stop_on_failure is False

    def test_factory_function(self):
        """Test the factory function."""
        from karaoke_gen.pipeline.executors.local import create_local_executor
        
        executor = create_local_executor()
        assert executor is not None

    @pytest.mark.asyncio
    async def test_run_stage_validates_inputs(self):
        """Test that run_stage validates inputs."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            @property
            def required_inputs(self):
                return ["missing_stage"]
            
            async def execute(self, context):
                return StageResult(status=StageStatus.COMPLETED)
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        executor = LocalExecutor()
        result = await executor.run_stage(TestStage(), context)
        
        assert result.failed is True
        assert "missing required inputs" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_run_stage_success(self):
        """Test running a successful stage."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        class TestStage(PipelineStage):
            @property
            def name(self):
                return "test"
            
            async def execute(self, context):
                return StageResult(
                    status=StageStatus.COMPLETED,
                    outputs={"result": "success"},
                )
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        executor = LocalExecutor()
        result = await executor.run_stage(TestStage(), context)
        
        assert result.success is True
        assert result.outputs == {"result": "success"}
        # Outputs should be stored in context
        assert context.stage_outputs.get("test") == {"result": "success"}

    @pytest.mark.asyncio
    async def test_run_pipeline_executes_stages_in_order(self):
        """Test that run_pipeline executes stages in order."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        execution_order = []
        
        class Stage1(PipelineStage):
            @property
            def name(self):
                return "stage1"
            
            async def execute(self, context):
                execution_order.append("stage1")
                return StageResult(status=StageStatus.COMPLETED)
        
        class Stage2(PipelineStage):
            @property
            def name(self):
                return "stage2"
            
            async def execute(self, context):
                execution_order.append("stage2")
                return StageResult(status=StageStatus.COMPLETED)
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        executor = LocalExecutor()
        results = await executor.run_pipeline([Stage1(), Stage2()], context)
        
        assert execution_order == ["stage1", "stage2"]
        assert results["stage1"].success
        assert results["stage2"].success

    @pytest.mark.asyncio
    async def test_run_pipeline_stops_on_failure(self):
        """Test that run_pipeline stops on failure when configured."""
        from karaoke_gen.pipeline.executors.local import LocalExecutor
        from karaoke_gen.pipeline.base import PipelineStage, StageResult, StageStatus
        from karaoke_gen.pipeline.context import PipelineContext
        
        execution_order = []
        
        class Stage1(PipelineStage):
            @property
            def name(self):
                return "stage1"
            
            async def execute(self, context):
                execution_order.append("stage1")
                return StageResult(
                    status=StageStatus.FAILED,
                    error_message="Stage 1 failed",
                )
        
        class Stage2(PipelineStage):
            @property
            def name(self):
                return "stage2"
            
            async def execute(self, context):
                execution_order.append("stage2")
                return StageResult(status=StageStatus.COMPLETED)
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        executor = LocalExecutor(stop_on_failure=True)
        results = await executor.run_pipeline([Stage1(), Stage2()], context)
        
        # Stage2 should not have executed
        assert execution_order == ["stage1"]
        assert results["stage1"].failed
        assert "stage2" not in results


class TestRemoteExecutor:
    """Tests for RemoteExecutor."""

    def test_executor_imports(self):
        """Test that the executor can be imported."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor, create_remote_executor
        assert RemoteExecutor is not None
        assert create_remote_executor is not None

    def test_create_executor(self):
        """Test creating a remote executor."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        
        executor = RemoteExecutor(
            service_url="https://api.example.com",
            auth_token="test-token",
        )
        
        assert executor.service_url == "https://api.example.com"
        assert executor.auth_token == "test-token"

    def test_create_executor_strips_trailing_slash(self):
        """Test that trailing slash is stripped from service URL."""
        from karaoke_gen.pipeline.executors.remote import RemoteExecutor
        
        executor = RemoteExecutor(service_url="https://api.example.com/")
        assert executor.service_url == "https://api.example.com"

    def test_factory_function(self):
        """Test the factory function."""
        from karaoke_gen.pipeline.executors.remote import create_remote_executor
        
        executor = create_remote_executor(
            service_url="https://api.example.com",
            auth_token="test-token",
        )
        
        assert executor is not None
        assert executor.service_url == "https://api.example.com"


class TestExecutorModuleExports:
    """Tests for module exports."""

    def test_executors_init_exports(self):
        """Test that executors __init__ exports all executors."""
        from karaoke_gen.pipeline.executors import (
            LocalExecutor,
            RemoteExecutor,
            create_local_executor,
            create_remote_executor,
        )
        
        assert LocalExecutor is not None
        assert RemoteExecutor is not None
        assert create_local_executor is not None
        assert create_remote_executor is not None
