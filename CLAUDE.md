# Development Guidelines for Claude Code

## **PDCA Development Methodology**

This project follows **Plan → Do → Check → Act** methodology for all feature development work.

### **Core Principles**

1. **Smallest Increment Rule**: Each commit should represent the smallest possible functional improvement
2. **Incremental Validation**: Test and validate after every increment before proceeding
3. **Test Evidence**: Archive validation results for each increment
4. **Rollback Strategy**: Each commit creates a rollback point if increment fails

### **Feature Development Structure**

All feature development work should be organized in:
```
feature_development/
  feature_name/
    FEATURE_PLAN.md           # PDCA plan with increments
    sql_scripts/              # Database changes (if applicable)
    test_evidence/
      increment_1/            # Validation results for each increment
      increment_2/
      ...
```

### **PDCA Plan Template**

Each feature should include:

#### **Intent**
Clear statement of what the feature accomplishes and why.

#### **Success Criteria Checklist**
- [ ] Measurable, testable criteria
- [ ] Zero breaking changes requirement
- [ ] End-to-end validation requirement

#### **PDCA Incremental Implementation**
**Increment 1**: ✅/❌ COMPLETED (hash) - Description
- [x] Specific, testable task
- [x] Test evidence archived
- [x] Validation completed

**Increment 2**: ✅/❌ COMPLETED (hash) - Description  
- [x] Next smallest increment
- [x] Builds on previous increment
- [x] Independent validation

### **Commit Workflow**
After each increment:
1. **Update plan** - Mark increment as completed with commit hash
2. **Store test evidence** - Archive validation results
3. **Commit changes** - Descriptive message following PDCA phase
4. **Update tracking** - Plan reflects actual commit for reference

### **Merge Workflow Example**
When systematically merging branches (e.g., sql-system-prompt → sql-systemtool-prompt-registry):

**Increment 1**: Add foundational methods (sql_helper.py system prompt methods)
- Update merge plan with ✅ COMPLETED status and commit hash
- Archive validation evidence
- Commit with descriptive PDCA message

**Increment 2**: Add supporting files (feature_development/ folder)
- Copy entire directory structure from source branch
- Commit as separate increment for rollback capability
- Update plan tracking with commit reference

### **Branch Strategy**
- **feature branches**: Use for PDCA development work
- **All branches**: Include `feature_development/` folder in commits for tracking
- **Merge strategy**: Careful file-by-file integration following PDCA principles
- **Production merges**: Manage feature_development folder inclusion separately during production deployment

### **Testing Requirements**
- Validate after each increment
- Archive test evidence before proceeding
- Compare before/after functionality
- Document any breaking changes or issues

## **Database Development**
- Use Azure CLI `sqlcmd` for database operations
- Create incremental SQL scripts for schema changes
- Test database connectivity after each change
- Store SQL scripts in feature development structure

## **Benefits of This Approach**
1. **Risk Mitigation**: Small increments reduce chance of major failures
2. **Audit Trail**: Complete history of development decisions
3. **Maintainability**: Clear documentation for future modifications
4. **Quality Assurance**: Validation at every step prevents regression

## **Azure OCR Service Specific Guidelines**

### **Environment Configuration**
- Never commit `.env` files with secrets
- Use existing Azure resources in `a1bgeneralresearch` resource group
- Maintain separation between local development and cloud deployment configs

### **API Development**
- Follow FastAPI best practices for endpoint design
- Implement proper error handling and logging
- Use async patterns for long-running document processing
- Maintain backward compatibility with existing scripts

### **Container Deployment**
- Use multi-stage Dockerfiles for optimal image size
- Implement health checks for container orchestration
- Configure environment variables for Azure resource integration
- Test locally before pushing to Azure Container Registry