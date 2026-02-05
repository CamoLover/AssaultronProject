# ============================================================================
# AUTONOMOUS AGENT ENDPOINTS
# ============================================================================

@app.route('/api/agent/task', methods=['POST'])
@limiter.limit("10 per minute")
def agent_task():
    """
    Submit a task to the autonomous agent.
    The agent will execute the task in the background.
    """
    data = request.get_json()
    task = data.get('task', '').strip()
    
    if not task:
        return jsonify({"error": "Empty task"}), 400
    
    # Generate task ID
    task_id = f"task_{int(time.time())}_{len(assaultron.agent_tasks)}"
    
    # Progress callback for updates
    progress_updates = []
    
    def progress_callback(update):
        progress_updates.append(update)
        assaultron.log_event(f"Agent [{task_id}]: {update.get('type', 'update')}", "AGENT")
    
    # Start agent task in background thread
    def run_agent_task():
        try:
            assaultron.log_event(f"Starting agent task: {task}", "AGENT")
            result = assaultron.agent_logic.execute_task(task, callback=progress_callback)
            
            # Store result
            assaultron.agent_tasks[task_id] = {
                "task": task,
                "status": "completed" if result.get("success") else "failed",
                "result": result,
                "progress": progress_updates,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Send final message to user
            if result.get("success"):
                final_message = f"Task completed: {result.get('result', 'Done')}"
            else:
                final_message = f"Task failed: {result.get('error', 'Unknown error')}"
            
            # Queue voice message if enabled
            if assaultron.voice_enabled:
                assaultron.voice_system.synthesize_async(final_message)
            
            assaultron.log_event(f"Agent task completed: {task_id}", "AGENT")
            
        except Exception as e:
            assaultron.log_event(f"Agent task error: {e}", "ERROR")
            assaultron.agent_tasks[task_id] = {
                "task": task,
                "status": "error",
                "error": str(e),
                "progress": progress_updates,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    
    # Start background thread
    thread = threading.Thread(target=run_agent_task, daemon=True)
    thread.start()
    
    # Initialize task tracking
    assaultron.agent_tasks[task_id] = {
        "task": task,
        "status": "running",
        "progress": progress_updates,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "Agent task started"
    })


@app.route('/api/agent/status/<task_id>')
def agent_status(task_id):
    """Get the status of an agent task."""
    if task_id not in assaultron.agent_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task_info = assaultron.agent_tasks[task_id]
    
    return jsonify({
        "task_id": task_id,
        "task": task_info["task"],
        "status": task_info["status"],
        "progress": task_info.get("progress", []),
        "result": task_info.get("result"),
        "error": task_info.get("error"),
        "timestamp": task_info["timestamp"]
    })


@app.route('/api/agent/tasks')
def agent_tasks():
    """List all agent tasks."""
    tasks = []
    for task_id, task_info in assaultron.agent_tasks.items():
        tasks.append({
            "task_id": task_id,
            "task": task_info["task"],
            "status": task_info["status"],
            "timestamp": task_info["timestamp"]
        })
    
    return jsonify({"tasks": tasks, "count": len(tasks)})


@app.route('/api/agent/stop/<task_id>', methods=['POST'])
def agent_stop(task_id):
    """Stop a running agent task."""
    if task_id not in assaultron.agent_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task_info = assaultron.agent_tasks[task_id]
    
    if task_info["status"] != "running":
        return jsonify({"error": "Task is not running"}), 400
    
    # Stop the agent
    assaultron.agent_logic.stop()
    task_info["status"] = "stopped"
    
    return jsonify({"success": True, "message": "Agent task stopped"})
